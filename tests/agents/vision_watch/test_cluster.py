"""Unit tests for the cluster node's derived tallies (no mocking at all)."""

import pytest

from hipeac_agents.agents.vision_watch.nodes import cluster
from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry, Finding, SourceCatalog


def entry(
    week: str = "2026-W24",
    finding_id: str = "f-1",
    source_class: str = "aggregators",
    tier: int = 2,
    region: str = "global",
    source_id: str = "robot-report",
) -> ClusterEntry:
    return ClusterEntry.model_validate(
        {
            "week": week,
            "finding_id": finding_id,
            "source_id": source_id,
            "source_class": source_class,
            "tier": tier,
            "region": region,
            "date": "2026-06-09",
            "note": "n",
            "url": "u",
        }
    )


@pytest.fixture
def catalog() -> SourceCatalog:
    return SourceCatalog.model_validate(
        {
            "sources": [
                {
                    "id": "robot-report",
                    "name": "r",
                    "url": "u",
                    "class": "aggregators",
                    "themes": [],
                    "region": "global",
                    "tier": 2,
                    "independence": "high",
                    "stream": "evidence",
                    "cadence": "weekly",
                },
                {
                    "id": "eu-fund",
                    "name": "e",
                    "url": "u",
                    "class": "eu-uptake",
                    "themes": [],
                    "region": "eu",
                    "tier": 2,
                    "independence": "low",
                    "stream": "evidence",
                    "cadence": "weekly",
                },
            ]
        }
    )


class TestTallies:
    def test_reach_counts_distinct_classes(self):
        assert (
            cluster.reach(
                [entry(source_class="aggregators"), entry(source_class="capital"), entry(source_class="aggregators")]
            )
            == 2
        )

    def test_persistence_counts_distinct_weeks(self):
        assert cluster.persistence([entry(week="2026-W23"), entry(week="2026-W24"), entry(week="2026-W24")]) == 2

    def test_evidence_strength_is_best_tier(self):
        assert cluster.evidence_strength([entry(tier=3), entry(tier=2)]) == 2

    def test_momentum_this_week_vs_prior_rate(self):
        entries = [entry(week="2026-W23"), entry(week="2026-W23"), entry(week="2026-W24")]

        count, prior_rate = cluster.momentum(entries, "2026-W24")

        assert count == 1
        assert prior_rate == 2.0  # 2 prior entries / 1 prior week

    def test_momentum_no_prior(self):
        count, prior_rate = cluster.momentum([entry()], "2026-W24")

        assert count == 1
        assert prior_rate == 0.0

    def test_spread_counts_distinct_regions(self):
        assert cluster.spread([entry(), entry(region="eu")]) == 2


class TestIndependenceShare:
    def test_all_low_independence(self, catalog):
        entries = [entry(source_id="eu-fund"), entry(source_id="eu-fund")]

        assert cluster.independence_share(entries, catalog) == 1.0

    def test_mixed(self, catalog):
        entries = [entry(source_id="robot-report"), entry(source_id="eu-fund")]

        assert cluster.independence_share(entries, catalog) == 0.5


class TestCandidateTrendThreshold:
    @pytest.mark.parametrize(
        ("entries", "expected"),
        [
            # 4 findings / 3 classes / 3 weeks / tier-2 anchor: crosses.
            (
                [
                    entry("2026-W22", "f-1", "aggregators"),
                    entry("2026-W23", "f-2", "capital", tier=2),
                    entry("2026-W24", "f-3", "programmes"),
                    entry("2026-W24", "f-4", "aggregators"),
                ],
                True,
            ),
            # Only 2 classes: below.
            (
                [
                    entry("2026-W22", "f-1", "aggregators"),
                    entry("2026-W23", "f-2", "aggregators"),
                    entry("2026-W23", "f-3", "aggregators"),
                    entry("2026-W24", "f-3", "capital"),
                ],
                False,
            ),
            # Only tier 3/4: below, whatever the tallies.
            (
                [
                    entry("2026-W22", "f-1", "aggregators", tier=3),
                    entry("2026-W23", "f-2", "capital", tier=3),
                    entry("2026-W24", "f-3", "programmes", tier=4),
                    entry("2026-W24", "f-4", "aggregators", tier=3),
                ],
                False,
            ),
            # Only 2 weeks: below.
            (
                [
                    entry("2026-W23", "f-1", "aggregators"),
                    entry("2026-W23", "f-2", "capital"),
                    entry("2026-W24", "f-3", "programmes"),
                    entry("2026-W24", "f-4", "aggregators"),
                ],
                False,
            ),
        ],
    )
    def test_threshold(self, entries, expected):
        assert cluster.is_candidate_trend(entries) is expected


class TestTrendStatus:
    def test_below_threshold_is_emerging(self):
        assert cluster.trend_status([entry(), entry(week="2026-W23", finding_id="f-2")]) == "emerging"

    def test_at_threshold_is_candidate_trend(self):
        entries = [
            entry("2026-W22", "f-1", "aggregators"),
            entry("2026-W23", "f-2", "capital", tier=2),
            entry("2026-W24", "f-3", "programmes"),
            entry("2026-W24", "f-4", "aggregators"),
        ]
        assert cluster.trend_status(entries) == "candidate-trend"

    def test_well_past_threshold_is_strengthening(self):
        entries = [
            entry("2026-W17", "f-1", "aggregators", tier=1),
            entry("2026-W18", "f-2", "capital"),
            entry("2026-W19", "f-3", "programmes"),
            entry("2026-W20", "f-4", "aggregators"),
            entry("2026-W21", "f-5", "companies"),
            entry("2026-W22", "f-6", "standards"),
        ]
        assert cluster.trend_status(entries) == "strengthening"


class TestEntriesThrough:
    def test_excludes_entries_after_week(self):
        entries = [entry(week="2026-W24", finding_id="f-1"), entry(week="2026-W25", finding_id="f-2")]

        assert [e.finding_id for e in cluster.entries_through(entries, "2026-W24")] == ["f-1"]

    def test_includes_entries_up_to_and_including_week(self):
        entries = [
            entry(week="2026-W23", finding_id="f-1"),
            entry(week="2026-W24", finding_id="f-2"),
            entry(week="2026-W25", finding_id="f-3"),
        ]

        assert [e.finding_id for e in cluster.entries_through(entries, "2026-W24")] == ["f-1", "f-2"]


class TestStrongest:
    def test_picks_best_tier(self):
        best = entry(finding_id="f-1", tier=3)
        strongest_entry = ClusterEntry.model_validate({**best.model_dump(), "finding_id": "f-2", "tier": 1})

        assert cluster.strongest([best, strongest_entry]).finding_id == "f-2"

    def test_ties_broken_by_most_recent(self):
        older = ClusterEntry.model_validate({**entry(finding_id="f-1", tier=1).model_dump(), "date": "2026-06-01"})
        newer = ClusterEntry.model_validate({**entry(finding_id="f-2", tier=1).model_dump(), "date": "2026-06-09"})

        assert cluster.strongest([older, newer]).finding_id == "f-2"


class TestSortLeadCandidates:
    def _cluster(self, cid: str, entries: list[ClusterEntry]) -> Cluster:
        return Cluster.model_validate(
            {"id": cid, "name": cid.title(), "opened": "2026-W01", "entries": [e.model_dump() for e in entries]}
        )

    def test_this_weeks_tier_beats_lifetime_volume(self, catalog):
        # 30 lifetime tier-3 entries, only a weak tier-3 mention this week.
        heavy_this_week = [entry(week="2026-W24", finding_id="h-24", source_class="aggregators", tier=3)]
        heavy_entries = [
            entry(week="2026-W20", finding_id=f"h-{i}", source_class="aggregators", tier=3) for i in range(29)
        ] + heavy_this_week
        # 2 tier-1 entries, both this week.
        fresh_entries = [
            entry(week="2026-W24", finding_id="f-1", source_class="aggregators", tier=1),
            entry(week="2026-W24", finding_id="f-2", source_class="capital", tier=1),
        ]
        candidates = [
            (self._cluster("heavy", heavy_entries), heavy_entries, heavy_this_week),
            (self._cluster("fresh", fresh_entries), fresh_entries, fresh_entries),
        ]

        ranked = cluster.sort_lead_candidates(candidates, "2026-W24", catalog)

        assert ranked[0][0].id == "fresh"

    def test_burst_beats_single_item_at_same_tier(self, catalog):
        single = [entry(week="2026-W24", finding_id="s-1", tier=1)]
        burst = [
            entry(week="2026-W24", finding_id="b-1", tier=1),
            entry(week="2026-W24", finding_id="b-2", source_class="capital", tier=1),
        ]
        candidates = [
            (self._cluster("single", single), single, single),
            (self._cluster("burst", burst), burst, burst),
        ]

        ranked = cluster.sort_lead_candidates(candidates, "2026-W24", catalog)

        assert ranked[0][0].id == "burst"


class TestLeadEmergence:
    """The lead is what is emerging, not what is already big."""

    def _cluster(self, cid: str, entries: list[ClusterEntry]) -> Cluster:
        return Cluster.model_validate(
            {"id": cid, "name": cid, "opened": "2026-W01", "entries": [e.model_dump() for e in entries]}
        )

    def test_forward_significance_beats_tier(self, catalog):
        solid = [entry(finding_id="s-1", tier=1).model_copy(update={"significance": 3})]
        consequential = [entry(finding_id="c-1", tier=3).model_copy(update={"significance": 5})]
        candidates = [
            (self._cluster("solid", solid), solid, solid),
            (self._cluster("consequential", consequential), consequential, consequential),
        ]

        assert cluster.sort_lead_candidates(candidates, "2026-W24", catalog)[0][0].id == "consequential"

    def test_story_reaching_new_classes_beats_one_repeating_itself(self, catalog):
        old = [entry(week="2026-W20", finding_id=f"o-{i}") for i in range(5)]
        repeating_now = [entry(finding_id="r-1")]
        spreading_now = [entry(finding_id="p-1", source_class="programmes", region="eu")]
        repeating = old + repeating_now
        spreading = [e.model_copy(update={"finding_id": f"x-{i}"}) for i, e in enumerate(old)] + spreading_now
        candidates = [
            (self._cluster("repeating", repeating), repeating, repeating_now),
            (self._cluster("spreading", spreading), spreading, spreading_now),
        ]

        assert cluster.novelty(spreading, "2026-W24") == 2
        assert cluster.novelty(repeating, "2026-W24") == 0
        assert cluster.sort_lead_candidates(candidates, "2026-W24", catalog)[0][0].id == "spreading"


class TestRanking:
    def _cluster(self, cid: str, entries: list[ClusterEntry]) -> tuple[Cluster, list[ClusterEntry]]:
        return Cluster.model_validate(
            {"id": cid, "name": cid.title(), "opened": "2026-W01", "entries": [e.model_dump() for e in entries]}
        ), entries

    def test_tier_first_then_reach_times_persistence(self, catalog):
        a_entries = [
            entry(week=f"2026-W2{i}", finding_id=f"a-{i}", source_class="aggregators", tier=1) for i in range(4)
        ]
        b_entries = [entry(week="2026-W24", finding_id=f"b-{i}", source_class="aggregators", tier=3) for i in range(4)]
        ranked = cluster.sort_ranked([self._cluster("b", b_entries), self._cluster("a", a_entries)], catalog)

        assert [c.id for c, _ in ranked] == ["a", "b"]

    def test_low_independence_discounted(self, catalog):
        eu_entries = [
            entry(week=f"2026-W2{i}", finding_id=f"e-{i}", source_class="eu-uptake", source_id="eu-fund")
            for i in range(4)
        ]
        world_entries = [entry(week=f"2026-W2{i}", finding_id=f"w-{i}", source_class="aggregators") for i in range(4)]
        ranked = cluster.sort_ranked([self._cluster("eu", eu_entries), self._cluster("w", world_entries)], catalog)

        assert [c.id for c, _ in ranked] == ["w", "eu"]


class TestGrouping:
    @staticmethod
    def finding(finding_id: str, theme_ids: list[str]) -> Finding:
        return Finding.model_validate(
            {
                "id": finding_id,
                "date": "2026-06-09",
                "title": "t",
                "url": "u",
                "source_id": "s",
                "region": "global",
                "tier": 2,
                "theme_ids": theme_ids,
                "summary": "s",
            }
        )

    def test_groups_by_finding_themes(self):
        findings = [
            self.finding("f-1", ["physical-ai"]),
            self.finding("f-2", ["physical-ai", "new-hardware"]),
            self.finding("f-3", []),
        ]

        grouped = cluster.group_key_by_theme(findings)

        assert {k: [f.id for f in v] for k, v in grouped.items()} == {
            "physical-ai": ["f-1", "f-2"],
            "new-hardware": ["f-2"],
        }
