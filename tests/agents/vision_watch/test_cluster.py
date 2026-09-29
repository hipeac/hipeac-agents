"""Unit tests for the cluster node's derived tallies (no mocking at all)."""

import pytest

from hipeac_agents.agents.vision_watch.nodes import cluster
from hipeac_agents.agents.vision_watch.schemas import Cluster, ClusterEntry, Finding, SourceCatalog


def entry(
    week: str = "2026-W24",
    finding_id: str = "f-1",
    source_class: str = "press",
    significance: int | None = None,
    region: str = "global",
    source_id: str = "robot-report",
) -> ClusterEntry:
    return ClusterEntry.model_validate(
        {
            "week": week,
            "finding_id": finding_id,
            "source_id": source_id,
            "source_class": source_class,
            "significance": significance,
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
            "classes": {
                "press": {"about": "Journalism.", "primary": False},
                "commentary": {"about": "Forums and opinion.", "primary": False},
                "programmes": {"about": "Public funders."},
                "research": {"about": "Research institutes."},
                "papers": {"about": "Research papers."},
                "companies": {"about": "Company newsrooms."},
                "standards": {"about": "Standards bodies."},
            },
            "sources": {
                "press": [{"id": "robot-report", "url": "u"}],
                "research": [{"id": "imec", "url": "u", "region": "eu"}],
            },
        }
    )


class TestTallies:
    def test_reach_counts_distinct_classes(self):
        assert (
            cluster.reach([entry(source_class="press"), entry(source_class="research"), entry(source_class="press")])
            == 2
        )

    def test_persistence_counts_distinct_weeks(self):
        assert cluster.persistence([entry(week="2026-W23"), entry(week="2026-W24"), entry(week="2026-W24")]) == 2

    def test_primary_source_is_a_primary_class(self, catalog):
        assert cluster.has_primary_source([entry(source_class="press"), entry(source_class="programmes")], catalog)
        assert not cluster.has_primary_source([entry(source_class="press"), entry(source_class="commentary")], catalog)
        assert not cluster.has_primary_source([entry(source_class="unlisted")], catalog), "unlisted is never primary"

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


class TestCurrentClasses:
    def test_source_reclassified_counts_in_its_new_class(self, catalog):
        recorded = [entry(source_id="imec", source_class="capital")]

        current = cluster.current_classes(recorded, catalog)

        assert current[0].source_class == "research"
        assert recorded[0].source_class == "capital", "the recorded entry is untouched"

    def test_source_removed_keeps_a_declared_recorded_class(self, catalog):
        gone = entry(source_id="old-source", source_class="companies")

        assert cluster.current_classes([gone], catalog)[0].source_class == "companies"

    def test_source_removed_with_an_undeclared_class_is_unlisted(self, catalog):
        sweep = entry(source_id="sweep", source_class="community")
        dropped = entry(source_id="old-source", source_class="aggregators")

        assert {e.source_class for e in cluster.current_classes([sweep, dropped], catalog)} == {cluster.UNLISTED_CLASS}

    def test_whole_log_is_copied_not_rewritten(self, catalog):
        from hipeac_agents.agents.vision_watch.schemas import ClusterLog

        log = ClusterLog.model_validate(
            {
                "theme": "new-hardware",
                "created": "2026-06-01",
                "clusters": [
                    {
                        "id": "c",
                        "name": "C",
                        "opened": "2026-W24",
                        "entries": [entry(source_id="imec", source_class="capital").model_dump()],
                    }
                ],
            }
        )

        current = cluster.log_with_current_classes(log, catalog)

        assert current.clusters[0].entries[0].source_class == "research"
        assert log.clusters[0].entries[0].source_class == "capital"


class TestCandidateTrendThreshold:
    @pytest.mark.parametrize(
        ("entries", "expected"),
        [
            # 4 findings / 3 classes / 3 weeks / a primary source: crosses.
            (
                [
                    entry("2026-W22", "f-1", "press"),
                    entry("2026-W23", "f-2", "research"),
                    entry("2026-W24", "f-3", "programmes"),
                    entry("2026-W24", "f-4", "press"),
                ],
                True,
            ),
            # Only 2 classes: below.
            (
                [
                    entry("2026-W22", "f-1", "press"),
                    entry("2026-W23", "f-2", "press"),
                    entry("2026-W23", "f-3", "press"),
                    entry("2026-W24", "f-3", "research"),
                ],
                False,
            ),
            # Only non-primary classes (press, commentary, unlisted): below, whatever the tallies.
            (
                [
                    entry("2026-W22", "f-1", "press"),
                    entry("2026-W23", "f-2", "commentary"),
                    entry("2026-W24", "f-3", "unlisted", region="eu"),
                    entry("2026-W24", "f-4", "commentary"),
                ],
                False,
            ),
            # Three classes, two of them not primary and one primary: crosses.
            (
                [
                    entry("2026-W22", "f-1", "press"),
                    entry("2026-W23", "f-2", "commentary"),
                    entry("2026-W24", "f-3", "papers"),
                    entry("2026-W24", "f-4", "press"),
                ],
                True,
            ),
            # Only 2 weeks: below.
            (
                [
                    entry("2026-W23", "f-1", "press"),
                    entry("2026-W23", "f-2", "research"),
                    entry("2026-W24", "f-3", "programmes"),
                    entry("2026-W24", "f-4", "press"),
                ],
                False,
            ),
        ],
    )
    def test_threshold(self, entries, expected, catalog):
        assert cluster.is_candidate_trend(entries, catalog) is expected


class TestTrendStatus:
    def test_below_threshold_is_emerging(self, catalog):
        assert cluster.trend_status([entry(), entry(week="2026-W23", finding_id="f-2")], catalog) == "emerging"

    def test_at_threshold_is_candidate_trend(self, catalog):
        entries = [
            entry("2026-W22", "f-1", "press"),
            entry("2026-W23", "f-2", "research"),
            entry("2026-W24", "f-3", "programmes"),
            entry("2026-W24", "f-4", "press"),
        ]
        assert cluster.trend_status(entries, catalog) == "candidate-trend"

    def test_well_past_threshold_is_strengthening(self, catalog):
        entries = [
            entry("2026-W17", "f-1", "press"),
            entry("2026-W18", "f-2", "research"),
            entry("2026-W19", "f-3", "programmes"),
            entry("2026-W20", "f-4", "press"),
            entry("2026-W21", "f-5", "companies"),
            entry("2026-W22", "f-6", "standards"),
        ]
        assert cluster.trend_status(entries, catalog) == "strengthening"


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
    def test_picks_most_significant(self):
        routine = entry(finding_id="f-1", significance=2)
        consequential = entry(finding_id="f-2", significance=4)

        assert cluster.strongest([routine, consequential]).finding_id == "f-2"

    def test_ties_broken_by_most_recent(self):
        older = ClusterEntry.model_validate(
            {**entry(finding_id="f-1", significance=4).model_dump(), "date": "2026-06-01"}
        )
        newer = ClusterEntry.model_validate(
            {**entry(finding_id="f-2", significance=4).model_dump(), "date": "2026-06-09"}
        )

        assert cluster.strongest([older, newer]).finding_id == "f-2"


class TestSortLeadCandidates:
    def _cluster(self, cid: str, entries: list[ClusterEntry]) -> Cluster:
        return Cluster.model_validate(
            {"id": cid, "name": cid.title(), "opened": "2026-W01", "entries": [e.model_dump() for e in entries]}
        )

    def test_new_story_beats_lifetime_volume(self, catalog):
        # 30 lifetime entries, only a routine mention this week.
        heavy_this_week = [entry(week="2026-W24", finding_id="h-24", significance=2)]
        heavy_entries = [
            entry(week="2026-W20", finding_id=f"h-{i}", significance=3) for i in range(29)
        ] + heavy_this_week
        # A new story, significant, this week.
        fresh_entries = [
            entry(week="2026-W24", finding_id="f-1", significance=4),
            entry(week="2026-W24", finding_id="f-2", source_class="research", significance=4),
        ]
        candidates = [
            (self._cluster("heavy", heavy_entries), heavy_entries, heavy_this_week),
            (self._cluster("fresh", fresh_entries), fresh_entries, fresh_entries),
        ]

        ranked = cluster.sort_lead_candidates(candidates, "2026-W24", catalog)

        assert ranked[0][0].id == "fresh"

    def test_burst_beats_single_item_at_same_significance(self, catalog):
        single = [entry(week="2026-W24", finding_id="s-1", significance=4)]
        burst = [
            entry(week="2026-W24", finding_id="b-1", significance=4),
            entry(week="2026-W24", finding_id="b-2", significance=4),
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

    def test_consequential_beats_solid(self, catalog):
        """Spreading to new kinds of source beats a loud entry from a kind already there."""
        earlier = [entry(week="2026-W20", finding_id=f"e-{i}") for i in range(3)]
        spreading_now = [
            entry(finding_id="s-1", source_class="programmes"),
            entry(finding_id="s-2", source_class="research"),
        ]
        loud_now = [entry(finding_id="l-1", significance=5)]
        spreading = earlier + spreading_now
        loud = [e.model_copy(update={"finding_id": f"x-{i}"}) for i, e in enumerate(earlier)] + loud_now
        candidates = [
            (self._cluster("loud", loud), loud, loud_now),
            (self._cluster("spreading", spreading), spreading, spreading_now),
        ]

        assert cluster.sort_lead_candidates(candidates, "2026-W24", catalog)[0][0].id == "spreading"

    def test_broad_beats_loud(self, catalog):
        """At equal novelty, three kinds of source this week beat one significance-5 item."""
        broad = [
            entry(finding_id="b-1", source_class="press", significance=3),
            entry(finding_id="b-2", source_class="programmes", significance=3),
            entry(finding_id="b-3", source_class="research", significance=3),
        ]
        loud = [entry(finding_id="l-1", significance=5)]
        candidates = [
            (self._cluster("loud", loud), loud, loud),
            (self._cluster("broad", broad), broad, broad),
        ]

        assert cluster.sort_lead_candidates(candidates, "2026-W24", catalog)[0][0].id == "broad"

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

    def test_primary_sources_first_then_reach_times_persistence(self, catalog):
        commentary = [entry(week=f"2026-W2{i}", finding_id=f"c-{i}", source_class="press") for i in range(4)]
        primary = [entry(week="2026-W24", finding_id=f"p-{i}", source_class="programmes") for i in range(4)]
        wider = [entry(week=f"2026-W2{i}", finding_id=f"w-{i}", source_class="programmes") for i in range(4)]
        ranked = cluster.sort_ranked(
            [self._cluster("commentary", commentary), self._cluster("primary", primary), self._cluster("wider", wider)],
            catalog,
        )

        assert [c.id for c, _ in ranked] == ["wider", "primary", "commentary"]

    def test_primary_source_breaks_a_reach_and_persistence_tie(self, catalog):
        reported = [
            entry(week=f"2026-W2{i}", finding_id=f"r-{i}", source_class=c)
            for i, c in enumerate(["press", "commentary", "press", "commentary"])
        ]
        announced = [
            entry(week=f"2026-W2{i}", finding_id=f"a-{i}", source_class=c)
            for i, c in enumerate(["press", "programmes", "press", "programmes"])
        ]
        ranked = cluster.sort_ranked(
            [self._cluster("reported", reported), self._cluster("announced", announced)], catalog
        )

        assert [c.id for c, _ in ranked] == ["announced", "reported"]


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


class TestClusterIndexText:
    def test_recent_clusters_keep_notes_old_ones_only_their_name(self):
        from hipeac_agents.agents.vision_watch.nodes.cluster.node import cluster_index_text

        recent = Cluster.model_validate(
            {
                "id": "recent",
                "name": "Recent story",
                "opened": "2026-W30",
                "entries": [entry(week="2026-W35").model_dump()],
            }
        )
        old = Cluster.model_validate(
            {"id": "old", "name": "Old story", "opened": "2026-W10", "entries": [entry(week="2026-W20").model_dump()]}
        )

        text = cluster_index_text({"recent": ("physical-ai", recent), "old": ("agentic-ai", old)}, "2026-W39")

        lines = dict(line.split(" ", 2)[1:] for line in text.splitlines())
        assert "Old story" in lines["old"] and "recent:" not in lines["old"]
        assert "Recent story" in lines["recent"] and "| recent: n" in lines["recent"]
