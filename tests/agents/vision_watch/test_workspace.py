"""Tests for the vision-watch workspace layer.

Covers the workspace rules as behaviour:
write-once for evidence files and digests, append-only for cluster logs.
"""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.schemas import (
    Cluster,
    ClusterEntry,
    Finding,
    FindingsFile,
    RejectedFile,
)
from hipeac_agents.agents.vision_watch.workspace import WorkspaceError


@pytest.fixture
def week(window) -> str:
    return workspace.weekly_label(window[1])


@pytest.fixture
def findings_file(week) -> FindingsFile:
    return FindingsFile(
        week=week,
        created=date(2026, 6, 11),
        findings=[
            Finding(
                id="f-2026-W24-01",
                date=date(2026, 6, 9),
                title="Some development",
                url="https://example.com/a",
                source_id="darpa-news",
                region="global",
                tier=2,
                summary="What happened.",
            )
        ],
    )


@pytest.fixture
def entry(week) -> ClusterEntry:
    return ClusterEntry(
        week=week,
        finding_id="f-2026-W24-01",
        source_id="robot-report",
        source_class="aggregators",
        tier=2,
        region="global",
        date=date(2026, 6, 9),
        note="A note.",
        url="https://example.com/a",
    )


@pytest.fixture
def cluster(week, entry) -> Cluster:
    return Cluster(id="humanoid-deployment", name="Humanoids in industry", opened=week, entries=[entry])


class TestWeeklyLabel:
    @pytest.mark.parametrize(
        ("day", "expected"),
        [
            (date(2026, 6, 6), "2026-W23"),
            (date(2026, 6, 12), "2026-W24"),
            (date(2026, 6, 10), "2026-W24"),
            (date(2026, 1, 1), "2026-W01"),
            (date(2025, 12, 28), "2025-W52"),
        ],
    )
    def test_label_uses_closing_friday_iso_week(self, day, expected):
        assert workspace.weekly_label(day) == expected

    def test_straddling_year_window_labels_by_closing_friday(self):
        window_start, window_end = workspace.current_window(date(2026, 1, 1))

        assert window_start == date(2025, 12, 27)
        assert window_end == date(2026, 1, 2)
        assert workspace.weekly_label(window_end) == "2026-W01"


class TestCurrentWindow:
    @pytest.mark.parametrize(
        ("today", "expected_start"),
        [
            (date(2026, 6, 6), date(2026, 6, 6)),
            (date(2026, 6, 9), date(2026, 6, 6)),
            (date(2026, 6, 12), date(2026, 6, 6)),
        ],
    )
    def test_window_starts_on_saturday(self, today, expected_start):
        window_start, window_end = workspace.current_window(today)

        assert window_start == expected_start
        assert window_start.weekday() == 5
        assert window_end.weekday() == 4
        assert (window_end - window_start).days == 6


class TestFindingsFile:
    def test_write_then_read_round_trip(self, data_dir, findings_file):
        path = workspace.write_findings_file(findings_file, data_dir)

        assert path.exists()
        parsed = workspace.read_findings_file(findings_file.week, data_dir)
        assert parsed == findings_file

    def test_read_missing_week_returns_none(self, data_dir):
        assert workspace.read_findings_file("2026-W01", data_dir) is None

    def test_write_once_violation(self, data_dir, findings_file):
        workspace.write_findings_file(findings_file, data_dir)

        with pytest.raises(WorkspaceError, match="write-once"):
            workspace.write_findings_file(findings_file, data_dir)


class TestRejectedFile:
    def test_write_once(self, data_dir, week):
        audit = RejectedFile(
            week=week,
            created=date(2026, 6, 11),
            rejected=[
                {
                    "url": "https://example.com/b",
                    "claimed_title": "Claimed",
                    "source_id": "sweep",
                    "reason": "title_mismatch",
                }
            ],
        )

        workspace.write_rejected_file(audit, data_dir)

        with pytest.raises(WorkspaceError):
            workspace.write_rejected_file(audit, data_dir)


class TestClusterLog:
    def test_append_cluster_creates_log_on_first_theme_cluster(self, data_dir, cluster, entry):
        workspace.append_cluster(cluster, theme="physical-ai", created=date(2026, 1, 8), data_dir=data_dir)

        log = workspace.read_cluster_log("physical-ai", data_dir)
        assert log is not None
        assert log.theme == "physical-ai"
        assert [c.id for c in log.clusters] == ["humanoid-deployment"]

    def test_append_existing_cluster_raises(self, data_dir, cluster, entry):
        workspace.append_cluster(cluster, theme="physical-ai", created=date(2026, 1, 8), data_dir=data_dir)

        # Its own type: the cluster node recovers from this one and re-raises
        # every other append-only violation.
        with pytest.raises(workspace.ClusterExistsError, match="already exists"):
            workspace.append_cluster(cluster, theme="physical-ai", created=date(2026, 1, 8), data_dir=data_dir)

    def test_append_entry_to_existing_cluster(self, data_dir, cluster, entry, week):
        workspace.append_cluster(cluster, theme="physical-ai", created=date(2026, 1, 8), data_dir=data_dir)
        second = entry.model_copy(
            update={"finding_id": "f-2026-W25-01", "week": "2026-W25", "url": "https://example.com/b"}
        )

        workspace.append_cluster_entry("physical-ai", "humanoid-deployment", second, data_dir)

        log = workspace.read_cluster_log("physical-ai", data_dir)
        assert [e.finding_id for e in log.clusters[0].entries] == [
            "f-2026-W24-01",
            "f-2026-W25-01",
        ]

    def test_append_entry_to_unknown_cluster_raises(self, data_dir, entry):
        workspace.append_cluster(
            Cluster(id="other", name="Other", opened="2026-W24", entries=[]),
            theme="physical-ai",
            created=date(2026, 1, 8),
            data_dir=data_dir,
        )

        # A missing cluster is a real error, not a re-run: it stays a plain
        # WorkspaceError so the cluster node lets it through.
        with pytest.raises(WorkspaceError, match="does not exist"):
            workspace.append_cluster_entry("physical-ai", "humanoid-deployment", entry, data_dir)
        assert not isinstance(WorkspaceError("x"), workspace.EntryAlreadyRecordedError)

    def test_append_duplicate_finding_raises(self, data_dir, cluster, entry):
        workspace.append_cluster(cluster, theme="physical-ai", created=date(2026, 1, 8), data_dir=data_dir)

        with pytest.raises(workspace.EntryAlreadyRecordedError, match="f-2026-W24-01"):
            workspace.append_cluster_entry("physical-ai", "humanoid-deployment", entry, data_dir)

    def test_append_duplicate_url_raises_the_same_type(self, data_dir, cluster, entry):
        """A finding re-entering under a new id but the same URL is still a
        re-run, so it must be the recoverable type too."""
        workspace.append_cluster(cluster, theme="physical-ai", created=date(2026, 1, 8), data_dir=data_dir)
        same_url = entry.model_copy(update={"finding_id": "f-2026-W25-09", "week": "2026-W25"})

        with pytest.raises(workspace.EntryAlreadyRecordedError, match="url"):
            workspace.append_cluster_entry("physical-ai", "humanoid-deployment", same_url, data_dir)


class TestWeeklyDigest:
    def test_write_once(self, data_dir, week):
        path = workspace.write_weekly_digest(week, "# Digest", data_dir)

        assert path.name == f"digest-{week}.md"
        with pytest.raises(WorkspaceError):
            workspace.write_weekly_digest(week, "# Again", data_dir)


class TestConfig:
    def test_read_themes_in_config_order(self, data_dir):
        themes = workspace.read_themes(data_dir)

        assert themes[0].theme == "next-computing-paradigm"
        assert themes[-1].theme == "agentic-ai"

    def test_missing_config_raises_clear_error(self, tmp_path):
        with pytest.raises(WorkspaceError, match="human-owned config"):
            workspace.read_themes(tmp_path)

    def test_operator_copy_overrides(self, data_dir):
        config = workspace.workspace_root(data_dir) / "config" / "themes.yaml"
        config.write_text(
            "themes:\n  - theme: custom\n    description: Custom theme.\n",
            encoding="utf-8",
        )

        themes = workspace.read_themes(data_dir)

        assert [t.theme for t in themes] == ["custom"]

    def test_source_catalog_read(self, data_dir):
        catalog = workspace.read_source_catalog(data_dir)

        ids = [s.id for s in catalog.sources]
        assert "darpa-news" in ids
        assert "fabricated-knowledge" in ids

    def test_list_weeks_sorted(self, data_dir, findings_file, week):
        workspace.write_findings_file(findings_file, data_dir)
        earlier = findings_file.model_copy(
            update={"week": "2026-W23"},
            deep=True,
        )
        workspace.write_findings_file(earlier, data_dir)

        weeks = workspace.list_weeks(data_dir)

        assert weeks == ["2026-W23", week]


class TestPurgeWeek:
    """``--redo``: the one sanctioned non-append edit, always backed up."""

    @pytest.fixture
    def recorded_week(self, data_dir, findings_file, cluster, week):
        workspace.write_findings_file(findings_file, data_dir)
        workspace.write_grouping_plan(week, '{"assignments": []}', data_dir)
        workspace.write_weekly_digest(week, "# digest\n", data_dir)
        workspace.append_cluster(cluster, "physical-ai", date(2026, 6, 11), data_dir)
        later = cluster.model_copy(deep=True)
        later.id = "long-running"
        later.entries[0].week = "2026-W23"
        later.entries[0].finding_id = "f-2026-W23-01"
        later_entry = later.entries[0].model_copy(update={"week": week, "finding_id": "f-2026-W24-02"})
        later.entries.append(later_entry)
        workspace.append_cluster(later, "physical-ai", date(2026, 6, 11), data_dir)
        return week

    def test_harvest_redo_sets_evidence_digest_and_entries_aside(self, data_dir, recorded_week):
        backup = workspace.purge_week(recorded_week, keep_evidence=False, data_dir=data_dir)

        assert workspace.read_findings_file(recorded_week, data_dir) is None
        assert workspace.read_weekly_digest(recorded_week, data_dir) is None
        assert workspace.week_cluster_entry_count(recorded_week, data_dir) == 0
        log = workspace.read_cluster_log("physical-ai", data_dir)
        assert [c.id for c in log.clusters] == ["long-running"], "a cluster left empty is dropped"
        assert [e.week for e in log.clusters[0].entries] == ["2026-W23"], "other weeks are untouched"
        assert (backup / "evidence" / recorded_week / "findings.json").exists()
        assert (backup / "digests" / "weekly" / f"digest-{recorded_week}.md").exists()
        assert (backup / "clusters" / "physical-ai-clusters.json").exists()

    def test_digest_redo_keeps_the_evidence(self, data_dir, recorded_week):
        backup = workspace.purge_week(recorded_week, keep_evidence=True, data_dir=data_dir)

        assert workspace.read_findings_file(recorded_week, data_dir) is not None
        assert workspace.read_grouping_plan(recorded_week, data_dir) is None
        assert workspace.read_weekly_digest(recorded_week, data_dir) is None
        assert (backup / "evidence" / recorded_week / "grouping.json").exists()

    def test_sent_marker_stays_so_a_redone_week_is_never_mailed_twice(self, data_dir, recorded_week):
        workspace.mark_weekly_digest_sent(recorded_week, "m-1", data_dir)

        workspace.purge_week(recorded_week, keep_evidence=True, data_dir=data_dir)

        assert workspace.weekly_digest_sent(recorded_week, data_dir)
