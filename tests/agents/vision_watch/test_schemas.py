"""Tests for the workspace-file schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from hipeac_agents.agents.vision_watch.schemas import (
    ClusterEntry,
    Finding,
    RejectedItem,
    SourceCatalog,
    SourceEntry,
    ThemeDef,
)


class TestFinding:
    def test_accepts_documented_fields(self):
        finding = Finding.model_validate(
            {
                "id": "f-2026-W24-01",
                "date": "2026-06-09",
                "title": "Some development",
                "url": "https://example.com/a",
                "source_id": "darpa-news",
                "region": "global",
                "tier": 2,
                "datapoint": "$900M",
                "summary": "What happened.",
            }
        )

        assert finding.date == date(2026, 6, 9)
        assert finding.tier == 2
        # Significance defaults to the gate scale's mid-point when unrecorded.
        assert finding.significance == 3

    @pytest.mark.parametrize("tier", [0, 5, "high"])
    def test_rejects_tier_outside_scale(self, tier):
        with pytest.raises(ValidationError):
            Finding.model_validate(
                {
                    "id": "f-2026-W24-01",
                    "date": "2026-06-09",
                    "title": "Some development",
                    "url": "https://example.com/a",
                    "source_id": "darpa-news",
                    "region": "global",
                    "tier": tier,
                    "summary": "What happened.",
                }
            )

    def test_rejects_unknown_region(self):
        with pytest.raises(ValidationError):
            Finding.model_validate(
                {
                    "id": "f-1",
                    "date": "2026-06-09",
                    "title": "t",
                    "url": "u",
                    "source_id": "s",
                    "region": "asia",
                    "tier": 2,
                    "summary": "s",
                }
            )


class TestRejectedItem:
    @pytest.mark.parametrize(
        "reason",
        [
            "out_of_window",
            "off_theme",
            "duplicate",
            "url_404",
            "title_mismatch",
            "newsletter_mismatch",
            "board_tip_unresolved",
            "unverified_sweep",
            "source_cap",
        ],
    )
    def test_accepts_every_documented_reason(self, reason):
        item = RejectedItem.model_validate({"url": "u", "claimed_title": "t", "source_id": "s", "reason": reason})

        assert item.reason == reason

    def test_rejects_undocumented_reason(self):
        with pytest.raises(ValidationError):
            RejectedItem.model_validate({"url": "u", "claimed_title": "t", "source_id": "s", "reason": "spicy"})


class TestClusterEntry:
    def test_captures_derived_tallying_fields(self):
        entry = ClusterEntry.model_validate(
            {
                "week": "2026-W01",
                "finding_id": "f-2026-W01-03",
                "source_id": "robot-report",
                "source_class": "aggregators",
                "tier": 2,
                "region": "global",
                "date": "2026-01-13",
                "note": "Mobileye $900M acquisition of Mentee Robotics",
                "url": "https://example.com/a",
            }
        )

        assert entry.source_class == "aggregators"
        assert entry.week == "2026-W01"


class TestSourceEntry:
    def test_minimal_entry_takes_defaults(self):
        entry = SourceEntry.model_validate(
            {
                "id": "darpa-news",
                "url": "https://www.darpa.mil/news",
                "class": "programmes",
                "tier": 2,
                "independence": "high",
            }
        )

        assert entry.name == "darpa-news"
        assert entry.region == "global"
        assert entry.web is True
        assert entry.newsletter is False
        assert entry.skip is None

    def test_senders_make_a_newsletter(self):
        entry = SourceEntry.model_validate(
            {
                "id": "semianalysis",
                "url": "https://semianalysis.com",
                "class": "aggregators",
                "tier": 4,
                "independence": "low",
                "senders": ["semianalysis@substack.com"],
                "web": False,
            }
        )

        assert entry.newsletter is True
        assert entry.web is False


class TestThemeDef:
    def test_question_with_optional_hints(self):
        theme = ThemeDef.model_validate(
            {
                "theme": "efficient-ai",
                "question": "Is the science-of-AI path delivering?",
                "why": "Smaller models keep Europe in the race.",
                "look_for": ["densing law", "small reasoning models"],
            }
        )

        assert theme.keywords == []
        assert theme.brief() == (
            "- efficient-ai: Is the science-of-AI path delivering? "
            "Why it matters: Smaller models keep Europe in the race. "
            "Look for: densing law, small reasoning models"
        )


class TestSourceCatalog:
    def test_grouped_file_flattens_with_class_defaults(self, data_dir):
        from hipeac_agents.agents.vision_watch import workspace

        catalog = workspace.read_source_catalog(data_dir)
        by_id = {s.id: s for s in catalog.sources}

        assert by_id["darpa-news"].source_class == "programmes"
        assert (by_id["darpa-news"].tier, by_id["darpa-news"].independence) == (2, "high")
        assert (by_id["robot-report"].tier, by_id["robot-report"].independence) == (2, "high"), "overrides win"
        assert (by_id["eu-fund"].tier, by_id["eu-fund"].region) == (2, "eu")
        assert by_id["fabricated-knowledge"].newsletter is True

    def test_source_without_class_defaults_needs_its_own_tier(self):
        with pytest.raises(ValueError):
            SourceCatalog.model_validate({"sources": {"companies": [{"id": "x", "url": "https://x"}]}})
