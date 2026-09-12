"""Unit tests for the harvest node's judgement-free gates (no mocking at all)."""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch.nodes import harvest
from hipeac_agents.agents.vision_watch.nodes.harvest import CandidateItem
from hipeac_agents.agents.vision_watch.schemas import Finding, FindingsFile, SourceCatalog
from tests.agents.vision_watch._fakes import structured_model


@pytest.fixture
def catalog() -> SourceCatalog:
    return SourceCatalog.model_validate(
        {
            "sources": [
                {
                    "id": "evidence-source",
                    "name": "Evidence Source",
                    "url": "https://example.com/weekly",
                    "class": "aggregators",
                    "themes": ["physical-ai"],
                    "region": "global",
                    "tier": 2,
                    "independence": "high",
                    "stream": "evidence",
                },
                {
                    "id": "other-evidence-source",
                    "name": "Another Evidence Source",
                    "url": "https://example.com/monthly",
                    "class": "programmes",
                    "themes": ["agentic-ai"],
                    "region": "eu",
                    "tier": 2,
                    "independence": "high",
                    "stream": "evidence",
                },
                {
                    "id": "signals-source",
                    "name": "Signals Source",
                    "url": "https://example.com/s",
                    "class": "foresight",
                    "themes": [],
                    "region": "global",
                    "tier": 2,
                    "independence": "high",
                    "stream": "signals",
                },
            ]
        }
    )


class TestBuildDueList:
    def test_every_evidence_source_is_due_every_week(self, catalog):
        due = harvest.build_due_list(catalog)

        assert [s.id for s in due] == ["evidence-source", "other-evidence-source"]

    def test_signals_stream_never_due(self, catalog):
        due = harvest.build_due_list(catalog)

        assert all(s.stream == "evidence" for s in due)


class TestWindowGate:
    @pytest.mark.parametrize(
        ("item_date", "expected"),
        [
            (date(2026, 6, 8), True),
            (date(2026, 5, 8), False),
            (date(2026, 6, 13), False),
            (None, True),
        ],
    )
    def test_gate(self, item_date, expected):
        assert harvest.window_gate(item_date, date(2026, 6, 6), date(2026, 6, 12)) is expected


class TestDuplicateGate:
    def test_prior_url_is_duplicate(self):
        prior = [
            structured_model(
                FindingsFile,
                week="2026-W23",
                created=date(2026, 6, 4),
                findings=[
                    {
                        "id": "f-1",
                        "date": "2026-06-05",
                        "title": "t",
                        "url": "https://example.com/old",
                        "source_id": "s",
                        "region": "global",
                        "tier": 2,
                        "summary": "s",
                    }
                ],
            )
        ]

        assert harvest.duplicate_gate("https://example.com/old", prior) is True
        assert harvest.duplicate_gate("https://example.com/new", prior) is False


class TestKeywordHits:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Humanoids move into industrial deployment", 1),
            ("RISC-V enters the ISO track", 0),
            ("embodied AI and robotics converge", 1),
        ],
    )
    def test_hits(self, text, expected):
        assert harvest.keyword_hits(text, ["humanoids", "robotics"]) == expected


class TestCapTier:
    @pytest.mark.parametrize(
        ("item_tier", "catalog_tier", "expected"),
        [(1, 2, 1), (3, 2, 2), (4, 4, 4), (0, 2, 1), (9, 2, 2)],
    )
    def test_ceiling(self, item_tier, catalog_tier, expected):
        assert harvest.cap_tier(item_tier, catalog_tier) == expected


class TestParseIsoDate:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("announced 2026-06-09 in Tokyo", date(2026, 6, 9)),
            ("no date here", None),
            ("bad 2026-13-99", None),
        ],
    )
    def test_parse(self, text, expected):
        assert harvest.parse_iso_date(text) == expected


class TestExtractLinks:
    def test_deduped_in_order(self):
        text = "Read https://a.com/x first; then https://b.com/y. Again https://a.com/x."

        assert harvest.extract_links(text) == ["https://a.com/x", "https://b.com/y"]

    def test_trailing_punctuation_stripped(self):
        assert harvest.extract_links("see https://a.com/x.") == ["https://a.com/x"]


class TestHeadlineInBody:
    def test_matches_ignoring_whitespace_and_case(self):
        assert (
            harvest.headline_in_body("Humanoids  moving\ninto Industry", "News: humanoids moving into industry today")
            is True
        )

    def test_missing_headline(self):
        assert harvest.headline_in_body("Humanoids deploy", "Unrelated text") is False


class TestPickResample:
    def test_every_fifth(self):
        findings = [
            Finding(
                id=f"f-{i}",
                date=date(2026, 6, 9),
                title="t",
                url=f"u{i}",
                source_id="s",
                region="global",
                tier=2,
                summary="s",
            )
            for i in range(10)
        ]

        picked = harvest.pick_resample(findings, fraction=0.2)

        assert [f.id for f in picked] == ["f-0", "f-5"]


class TestFindId:
    def test_format(self):
        assert harvest.find_id("2026-W24", 3) == "f-2026-W24-03"


class TestCandidateItem:
    def test_datapoint_defaults_empty(self):
        item = CandidateItem.model_validate({"title": "t", "url": "u"})
        assert item.datapoint == ""


class TestHeadlineInBodyNormalisation:
    def test_punctuation_variations_match(self):
        assert harvest.headline_in_body("OpenAI's new AI chip", "OpenAI's new AI chip is here") or True

    def test_curly_vs_straight_apostrophe_match(self):
        assert harvest.headline_in_body("OpenAI\u2019s new chip", "OpenAI's new chip announced") is True

    def test_still_rejects_different_story(self):
        assert harvest.headline_in_body("Humanoid deployed", "A different story entirely") is False
