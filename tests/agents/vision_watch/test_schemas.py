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
        # Significance defaults to the gate scale's mid-point when unrecorded.
        assert finding.significance == 3

    def test_old_files_with_a_tier_still_read(self):
        """Tier was dropped; evidence written before still parses."""
        finding = Finding.model_validate(
            {
                "id": "f-2026-W24-01",
                "date": "2026-06-09",
                "title": "Some development",
                "url": "https://example.com/a",
                "source_id": "darpa-news",
                "region": "global",
                "tier": 2,
                "summary": "What happened.",
            }
        )

        assert not hasattr(finding, "tier")

    def test_old_files_with_a_direction_still_read(self):
        """Direction was dropped; evidence written before still parses."""
        finding = Finding.model_validate(
            {
                "id": "f-2026-W24-01",
                "date": "2026-06-09",
                "title": "Some development",
                "url": "https://example.com/a",
                "source_id": "darpa-news",
                "region": "global",
                "direction": "strengthens",
                "summary": "What happened.",
            }
        )

        assert "direction" not in finding.model_dump()

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
            "unresolved_link",
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
                "source_class": "press",
                "region": "global",
                "date": "2026-01-13",
                "note": "Mobileye $900M acquisition of Mentee Robotics",
                "url": "https://example.com/a",
            }
        )

        assert entry.source_class == "press"
        assert entry.week == "2026-W01"

    def test_old_logs_with_a_direction_still_read(self):
        entry = ClusterEntry.model_validate(
            {
                "week": "2026-W01",
                "finding_id": "f-2026-W01-03",
                "source_id": "robot-report",
                "source_class": "press",
                "region": "global",
                "date": "2026-01-13",
                "note": "n",
                "url": "https://example.com/a",
                "direction": "weakens",
            }
        )

        assert "direction" not in entry.model_dump()


class TestSourceEntry:
    def test_minimal_entry_takes_defaults(self):
        entry = SourceEntry.model_validate(
            {
                "id": "darpa-news",
                "url": "https://www.darpa.mil/news",
                "class": "programmes",
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
                "class": "analysis",
                "senders": ["semianalysis@substack.com"],
                "web": False,
            }
        )

        assert entry.newsletter is True
        assert entry.web is False


class TestThemeDef:
    def test_description_with_optional_questions_and_hints(self):
        theme = ThemeDef.model_validate(
            {
                "theme": "local-ai",
                "description": "Running capable AI on local, low-cost hardware.",
                "questions": ["Do small models close the gap?"],
                "look_for": ["densing law", "small reasoning models"],
            }
        )

        assert theme.keywords == []
        assert theme.brief() == (
            "- local-ai: Running capable AI on local, low-cost hardware. "
            "Open questions: Do small models close the gap? "
            "Look for: densing law, small reasoning models"
        )


class TestQuestionIds:
    def test_question_ids(self):
        theme = ThemeDef.model_validate(
            {"theme": "agentic-ai", "description": "Agents.", "questions": ["Gap?", "Small models?", "Protocols?"]}
        )

        assert theme.questions_by_id == {
            "agentic-ai.1": "Gap?",
            "agentic-ai.2": "Small models?",
            "agentic-ai.3": "Protocols?",
        }


class TestSourceCatalog:
    def test_grouped_file_flattens_under_declared_classes(self, data_dir):
        from hipeac_agents.agents.vision_watch import workspace

        catalog = workspace.read_source_catalog(data_dir)
        by_id = {s.id: s for s in catalog.sources}

        assert by_id["darpa-news"].source_class == "programmes"
        assert (by_id["eu-fund"].source_class, by_id["eu-fund"].region) == ("eu-institutions", "eu")
        assert by_id["fabricated-knowledge"].newsletter is True
        assert catalog.class_of("robot-report") == "press"
        assert catalog.class_of("sweep") is None

    def test_class_defaults(self):
        catalog = SourceCatalog.model_validate(
            {
                "classes": {"programmes": {"about": "Public funders."}},
                "sources": {"programmes": [{"id": "darpa-news", "url": "https://www.darpa.mil/news"}]},
            }
        )
        source = catalog.sources[0]

        assert (source.source_class, source.region, source.name) == ("programmes", "global", "darpa-news")
        assert catalog.is_primary("programmes")
        assert catalog.classes["programmes"].weekly_cap is None

    def test_non_primary_and_undeclared_classes(self):
        catalog = SourceCatalog.model_validate(
            {
                "classes": {"ai-news": {"about": "Curated AI-news digests.", "primary": False, "weekly_cap": 6}},
                "sources": {"ai-news": [{"id": "tldr", "url": "https://tldr.tech"}]},
            }
        )

        assert not catalog.is_primary("ai-news")
        assert not catalog.is_primary("unlisted"), "an undeclared class is never primary"
        assert catalog.classes["ai-news"].weekly_cap == 6

    def test_class_without_defaults_fails_naming_it(self):
        with pytest.raises(ValueError, match="companies"):
            SourceCatalog.model_validate({"sources": {"companies": [{"id": "x", "url": "https://x"}]}})

    def test_legacy_independence_is_ignored(self):
        catalog = SourceCatalog.model_validate(
            {
                "classes": {"eu-institutions": {"about": "EU-level bodies.", "independence": "low"}},
                "sources": {"eu-institutions": [{"id": "eu-fund", "url": "https://x", "independence": "high"}]},
            }
        )

        assert catalog.sources[0].source_class == "eu-institutions"
        assert not hasattr(catalog.sources[0], "independence")
