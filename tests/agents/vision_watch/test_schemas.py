"""Tests for the workspace-file schemas."""

from datetime import date

import pytest
from pydantic import ValidationError

from hipeac_agents.agents.vision_watch.schemas import (
    ClusterEntry,
    Finding,
    RejectedItem,
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
    def test_parses_catalog_yaml_fields(self):
        entry = SourceEntry.model_validate(
            {
                "id": "darpa-news",
                "name": "DARPA News",
                "url": "https://www.darpa.mil/news",
                "feed_url": "https://www.darpa.mil/rss",
                "class": "programmes",
                "themes": ["agentic-ai"],
                "region": "global",
                "tier": 2,
                "independence": "high",
                "stream": "evidence",
                "cadence": "monthly",
            }
        )

        assert entry.source_class == "programmes"
        assert entry.web is True
        assert entry.newsletter is False
        assert entry.bot_protected is False


class TestThemeDef:
    def test_parses_theme_fields(self):
        theme = ThemeDef.model_validate(
            {
                "theme": "physical-ai",
                "chapter": "technology-roadmap",
                "definition": "AI systems that interact with the physical world.",
                "keywords": ["embodied AI", "robotics"],
            }
        )

        assert theme.keywords == ["embodied AI", "robotics"]


class TestSourceCatalog:
    def test_parses_full_catalog(self, data_dir):
        from hipeac_agents.agents.vision_watch import workspace

        catalog = workspace.read_source_catalog(data_dir)

        assert catalog.meta["version"] == 6
        assert len(catalog.sources) > 0
