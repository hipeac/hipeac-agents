"""The vision-watch agent's workspace: folder map, file rules, config reads.

Filesystem access goes through the generic primitives in
``hipeac_agents.storage`` — this module maps the agent's schemas, folders,
and write-once / append-only rules onto them.

Folder map (under ``HIPEAC_AGENTS_DATA_DIR``)::

    config/                 themes.yaml, source-catalog.yaml (HUMAN-OWNED,
                            read-only to agents; the operator places them
                            here — agents raise a clear error if missing)
    evidence/<week>/        findings.json, rejected.json (write-once)
    cache/scrapes/<shard>/  Firecrawl markdown cache, content-addressed by
                            the canonical URL hash and shared across weeks
    clusters/               append-only, cross-week; one file per theme
    digests/weekly/         digest-YYYY-Www.md (write-once)
    digests/monthly/        digest-YYYY-MM.md (write-once)

The workspace rules are enforced as code, not convention:

1. Evidence files and digests are write-once: writing again raises.
2. ``append_cluster_entry`` and ``append_cluster`` are the only mutators of
   cluster logs, and both only ever add — never edit or remove. A reader
   derives momentum, reach, and persistence by tallying entries at read time;
   no such field is ever stored.
3. The one sanctioned exception is ``purge_week``: an operator-invoked redo
   (``--redo``) that moves a week's files into ``_backup/`` and removes that
   week's cluster entries, after backing the logs up.
"""

import json
import re
import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import yaml

from hipeac_agents.agents.vision_watch import schemas, settings
from hipeac_agents.agents.vision_watch.cadence import current_window, weekly_label
from hipeac_agents.storage import WorkspaceError, write_once


_WEEK_LABEL = re.compile(r"\d{4}-W\d{2}")


class ClusterExistsError(WorkspaceError):
    """Raised when a cluster id is already present in its theme's log.

    Its own type, not a message: a re-run of the same week hits this as a
    matter of course and recovers by appending to the existing cluster, so
    callers must be able to tell it apart from a real append-only violation.
    """


class EntryAlreadyRecordedError(WorkspaceError):
    """Raised when a finding is already recorded in the cluster it targets.

    Matched on the finding id or on its URL — either way the entry is already
    in the log, which makes re-running a week a no-op rather than an error.
    """


# --------------------------------------------------------------------------- #
# Paths and naming
# --------------------------------------------------------------------------- #


def workspace_root(data_dir: str | None = None) -> Path:
    """Return the workspace root directory.

    :param data_dir: Optional override of ``HIPEAC_AGENTS_DATA_DIR``; used by
        tests to point the workspace at a throwaway directory.
    :returns: The workspace root as a ``Path``.
    """
    return Path(data_dir or settings.DATA_DIR)


def week_dir(week: str, data_dir: str | None = None) -> Path:
    """Return a week's evidence directory.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: The ``evidence/<week>`` directory as a ``Path``.
    """
    return workspace_root(data_dir) / "evidence" / week


def findings_dir(week: str, data_dir: str | None = None) -> Path:
    """Return a week's evidence directory (findings and rejected live here).

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: The ``evidence/<week>`` directory as a ``Path``.
    """
    return week_dir(week, data_dir)


def clusters_dir(data_dir: str | None = None) -> Path:
    """Return the append-only cluster-log directory.

    Cluster logs are cross-week working memory — append-only, never reset —
    so they live at the workspace root, not under the weekly ``evidence/``.

    :param data_dir: Optional workspace-root override.
    :returns: The ``clusters`` directory as a ``Path``.
    """
    return workspace_root(data_dir) / "clusters"


def weekly_digest_dir(data_dir: str | None = None) -> Path:
    """Return the weekly pulse digest directory.

    :param data_dir: Optional workspace-root override.
    :returns: The ``digests/weekly`` directory as a ``Path``.
    """
    return workspace_root(data_dir) / "digests" / "weekly"


def monthly_digest_dir(data_dir: str | None = None) -> Path:
    """Return the monthly synthesis digest directory.

    :param data_dir: Optional workspace-root override.
    :returns: The ``digests/monthly`` directory as a ``Path``.
    """
    return workspace_root(data_dir) / "digests" / "monthly"


def monthly_digest_filename(month: str) -> str:
    """Return the monthly digest filename for a month.

    :param month: A calendar month as ``"2026-07"``.
    :returns: ``"digest-2026-07.md"``.
    """
    return f"digest-{month}.md"


def findings_path(week: str, data_dir: str | None = None) -> Path:
    """Return the findings file path for a week label.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: ``"evidence/<week>/findings.json"`` as a ``Path``.
    """
    return week_dir(week, data_dir) / "findings.json"


def rejected_path(week: str, data_dir: str | None = None) -> Path:
    """Return the rejected-audit file path for a week label.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: ``"evidence/<week>/rejected.json"`` as a ``Path``.
    """
    return week_dir(week, data_dir) / "rejected.json"


def grouping_path(week: str, data_dir: str | None = None) -> Path:
    """Return the grouping-plan file path for a week label.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: ``"evidence/<week>/grouping.json"`` as a ``Path``.
    """
    return week_dir(week, data_dir) / "grouping.json"


def write_sources_file(file: schemas.SourcesFile, data_dir: str | None = None) -> Path:
    """Write the week's per-source harvest report (write-once)."""
    return write_once(week_dir(file.week, data_dir) / "sources.json", file.model_dump_json(indent=2))


def read_sources_file(week: str, data_dir: str | None = None) -> schemas.SourcesFile | None:
    """Read a week's per-source harvest report.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: The report, or ``None`` when the week has none (harvested before reports existed).
    """
    path = week_dir(week, data_dir) / "sources.json"
    return schemas.SourcesFile.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def write_health(file: schemas.HealthFile, markdown: str, data_dir: str | None = None) -> Path:
    """Write a week's source-health labels and their readable report (write-once).

    :param file: The labels.
    :param markdown: The rendered report.
    :param data_dir: Optional workspace-root override.
    :returns: The markdown report's path.
    """
    write_once(week_dir(file.week, data_dir) / "health.json", file.model_dump_json(indent=2))
    return write_once(week_dir(file.week, data_dir) / "health.md", markdown)


def read_health_file(week: str, data_dir: str | None = None) -> schemas.HealthFile | None:
    """Read a week's source-health labels.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: The labels, or ``None`` when the week has no health report.
    """
    path = week_dir(week, data_dir) / "health.json"
    return schemas.HealthFile.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def write_grouping_plan(week: str, plan_json: str, data_dir: str | None = None) -> Path:
    """Record the week's grouping decision (write-once).

    The grouping judgement is made once per week and reused on rerun, like
    every other recorded judgement in the system.

    :param week: A week label such as ``"2026-W24"``.
    :param plan_json: The serialised grouping plan.
    :param data_dir: Optional workspace-root override.
    :returns: The written path.
    :raises WorkspaceError: If the file already exists.
    """
    return write_once(grouping_path(week, data_dir), plan_json)


def read_grouping_plan(week: str, data_dir: str | None = None):
    """Read a recorded grouping plan, if the week has one.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: The recorded plan, or ``None``.
    """
    from hipeac_agents.agents.vision_watch.nodes.cluster.models import GroupingPlan

    path = grouping_path(week, data_dir)
    if not path.exists():
        return None
    return GroupingPlan.model_validate_json(path.read_text(encoding="utf-8"))


def cache_root(data_dir: str | None = None) -> Path:
    """Return the workspace-level cache root.

    Content-addressed by the SHA-256 of the canonical URL, so pages fetched
    once are reused across weeks and runs; each entry keeps the URL, title,
    markdown, and fetch timestamp as evidence. Sharded under
    ``scrapes/<2-letter>/`` to keep per-directory file counts low.

    :param data_dir: Optional workspace-root override.
    :returns: The ``cache`` directory as a ``Path``.
    """
    return workspace_root(data_dir) / "cache"


def feed_snapshot_path(week: str, source_id: str, data_dir: str | None = None) -> Path:
    """Return the path of one source's feed snapshot for a week.

    Snapshots live under the cache, not the week's evidence: they are
    mutable while the week is open, and a ``--redo`` must not discard them.

    :param week: A week label such as ``"2026-W24"``.
    :param source_id: The catalog source id.
    :param data_dir: Optional workspace-root override.
    :returns: ``cache/feed-snapshots/<week>/<source>.json`` as a ``Path``.
    """
    return cache_root(data_dir) / "feed-snapshots" / week / f"{source_id}.json"


def read_feed_snapshot(week: str, source_id: str, data_dir: str | None = None) -> list:
    """Read the feed entries captured for a source during a week.

    :param week: A week label such as ``"2026-W24"``.
    :param source_id: The catalog source id.
    :param data_dir: Optional workspace-root override.
    :returns: The captured candidates, empty when none were captured.
    """
    from hipeac_agents.agents.vision_watch.nodes.harvest.models import CandidateItem

    path = feed_snapshot_path(week, source_id, data_dir)
    if not path.exists():
        return []
    return [CandidateItem.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def write_feed_snapshot(week: str, source_id: str, items: list, data_dir: str | None = None) -> Path:
    """Replace a source's feed snapshot for a week (mutable while the week is open).

    :param week: A week label such as ``"2026-W24"``.
    :param source_id: The catalog source id.
    :param items: The candidates to keep.
    :param data_dir: Optional workspace-root override.
    :returns: The written path.
    """
    path = feed_snapshot_path(week, source_id, data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item.model_dump() for item in items], indent=2), encoding="utf-8")
    return path


def cluster_filename(theme: str) -> str:
    """Return the cluster-log filename for a theme.

    Named ``<theme>-clusters.json`` — plural, because each file holds the
    theme's many development clusters; the filename mirrors that grouping.

    :param theme: The theme id, e.g. ``"physical-ai"``.
    :returns: ``"physical-ai-clusters.json"``.
    """
    return f"{theme}-clusters.json"


def digest_filename(week: str) -> str:
    """Return the weekly digest filename for a week label.

    :param week: A week label such as ``"2026-W24"``.
    :returns: ``"digest-2026-W24.md"``.
    """
    return f"digest-{week}.md"


# --------------------------------------------------------------------------- #
# Weekly evidence files
# --------------------------------------------------------------------------- #


def write_findings_file(file: schemas.FindingsFile, data_dir: str | None = None) -> Path:
    """Write the week's findings file (write-once)."""
    return write_once(findings_path(file.week, data_dir), file.model_dump_json(indent=2))


def read_findings_file(week: str, data_dir: str | None = None) -> schemas.FindingsFile | None:
    """Read a weekly findings file.

    :param week: A week label such as ``"2026-W24"`.
    :param data_dir: Optional workspace-root override.
    :returns: The parsed findings file, or ``None`` if the week has no file.
    """
    path = findings_path(week, data_dir)

    if not path.exists():
        return None

    return schemas.FindingsFile.model_validate_json(path.read_text(encoding="utf-8"))


def list_weeks(data_dir: str | None = None) -> list[str]:
    """List the week labels that have findings files, oldest first.

    :param data_dir: Optional workspace-root override.
    :returns: Sorted week labels.
    """
    evidence = workspace_root(data_dir) / "evidence"

    return sorted(
        path.parent.name for path in evidence.glob("*/findings.json") if _WEEK_LABEL.fullmatch(path.parent.name)
    )


def read_all_findings(data_dir: str | None = None) -> list[schemas.FindingsFile]:
    """Read every weekly findings file, oldest first.

    Duplicate detection reads all recorded history — a story found weeks ago
    must not re-enter through sweep or newsletter channels.

    :param data_dir: Optional workspace-root override.
    :returns: All parsed findings files.
    """
    files = []
    for week in list_weeks(data_dir):
        if file := read_findings_file(week, data_dir):
            files.append(file)
    return files


def write_rejected_file(file: schemas.RejectedFile, data_dir: str | None = None) -> Path:
    """Write the week's rejected-audit file (write-once)."""
    return write_once(rejected_path(file.week, data_dir), file.model_dump_json(indent=2))


def read_rejected_file(week: str, data_dir: str | None = None) -> schemas.RejectedFile | None:
    """Read a weekly rejected-audit file.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: The parsed rejected file, or ``None`` if the week has no file.
    """
    path = rejected_path(week, data_dir)

    if not path.exists():
        return None

    return schemas.RejectedFile.model_validate_json(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Cluster logs (the one append-only file type)
# --------------------------------------------------------------------------- #


def _read_cluster_log(theme: str, data_dir: str | None) -> schemas.ClusterLog:
    path = clusters_dir(data_dir) / cluster_filename(theme)

    if not path.exists():
        raise WorkspaceError(f"cluster log for theme '{theme}' does not exist yet")

    return schemas.ClusterLog.model_validate_json(path.read_text(encoding="utf-8"))


def read_cluster_log(theme: str, data_dir: str | None = None) -> schemas.ClusterLog | None:
    """Read a theme's cluster log.

    :param theme: The theme id, e.g. ``"physical-ai"``.
    :param data_dir: Optional workspace-root override.
    :returns: The parsed log, or ``None`` if the theme has no log yet.
    """
    path = clusters_dir(data_dir) / cluster_filename(theme)

    if not path.exists():
        return None

    return schemas.ClusterLog.model_validate_json(path.read_text(encoding="utf-8"))


def create_cluster_log(log: schemas.ClusterLog, data_dir: str | None = None) -> Path:
    """Create a theme's cluster log (write-once, first cluster only).

    :param log: The log to create; must have no clusters beyond its first.
    :param data_dir: Optional workspace-root override.
    :returns: The written path.
    :raises WorkspaceError: If the log already exists.
    """
    path = clusters_dir(data_dir) / cluster_filename(log.theme)
    return write_once(path, log.model_dump_json(indent=2))


def append_cluster(cluster: schemas.Cluster, theme: str, created: date, data_dir: str | None = None) -> None:
    """Append a new cluster object to a theme's log, creating the log if needed.

    This is one of the two mutators of cluster logs; it only ever adds a new
    cluster object — an existing cluster id raises.

    :param cluster: The cluster to append.
    :param theme: The theme id the cluster belongs to.
    :param created: Creation date recorded on a brand-new log.
    :param data_dir: Optional workspace-root override.
    :raises ClusterExistsError: If the cluster id already exists in the log.
    """
    path = clusters_dir(data_dir) / cluster_filename(theme)
    if path.exists():
        log = _read_cluster_log(theme, data_dir)
        if any(existing.id == cluster.id for existing in log.clusters):
            raise ClusterExistsError(f"cluster '{cluster.id}' already exists in theme '{theme}'")
        log.clusters.append(cluster)
        path.write_text(log.model_dump_json(indent=2), encoding="utf-8")
        return
    create_cluster_log(schemas.ClusterLog(theme=theme, created=created, clusters=[cluster]), data_dir)


def append_cluster_entry(theme: str, cluster_id: str, entry: schemas.ClusterEntry, data_dir: str | None = None) -> None:
    """Append one entry to an existing cluster — the only per-entry mutator.

    The entry is only ever added; never edited or removed.

    :param theme: The theme id, e.g. ``"physical-ai"``.
    :param cluster_id: The cluster the entry extends.
    :param entry: The entry to append.
    :param data_dir: Optional workspace-root override.
    :raises WorkspaceError: If the log or cluster does not exist.
    :raises EntryAlreadyRecordedError: If the finding is already recorded in
        the cluster, by id or by URL.
    """
    log = _read_cluster_log(theme, data_dir)
    cluster = next((c for c in log.clusters if c.id == cluster_id), None)

    if cluster is None:
        raise WorkspaceError(f"cluster '{cluster_id}' does not exist in theme '{theme}'")

    if any(existing.finding_id == entry.finding_id for existing in cluster.entries):
        raise EntryAlreadyRecordedError(f"finding '{entry.finding_id}' already in cluster '{cluster_id}'")
    if any(existing.url == entry.url for existing in cluster.entries):
        raise EntryAlreadyRecordedError(f"url '{entry.url}' already in cluster '{cluster_id}'")

    cluster.entries.append(entry)
    (clusters_dir(data_dir) / cluster_filename(theme)).write_text(log.model_dump_json(indent=2), encoding="utf-8")


def week_cluster_entry_count(week: str, data_dir: str | None = None) -> int:
    """Count the cluster entries recorded for a week, across every theme's log.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: The number of entries whose week is ``week``.
    """
    count = 0
    for path in sorted(clusters_dir(data_dir).glob("*-clusters.json")):
        log = schemas.ClusterLog.model_validate_json(path.read_text(encoding="utf-8"))
        count += sum(1 for cluster in log.clusters for entry in cluster.entries if entry.week == week)
    return count


def purge_week(week: str, keep_evidence: bool, data_dir: str | None = None) -> Path:
    """Set a week aside so it can be redone: the one sanctioned non-append edit.

    Moves the week's weekly digest and grouping plan (and, unless
    ``keep_evidence``, its whole evidence folder) into
    ``_backup/<week>-<timestamp>/``, backs up every cluster log that has
    entries for the week, then removes those entries — dropping clusters
    left empty. Finding ids are reused when a week is harvested again, so
    leaving old entries behind would point them at different findings.
    A digest's sent marker stays: a redone week is never mailed twice.

    :param week: A week label such as ``"2026-W24"``.
    :param keep_evidence: Keep ``findings.json`` / ``rejected.json`` (a digest redo).
    :param data_dir: Optional workspace-root override.
    :returns: The backup directory.
    """
    backup = workspace_root(data_dir) / "_backup" / f"{week}-{datetime.now(UTC):%Y%m%dT%H%M%S}"
    backup.mkdir(parents=True)

    def _move(path: Path, relative: str) -> None:
        if path.exists():
            target = backup / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(path, target)

    if keep_evidence:
        _move(grouping_path(week, data_dir), f"evidence/{week}/grouping.json")
    else:
        _move(week_dir(week, data_dir), f"evidence/{week}")
    _move(weekly_digest_dir(data_dir) / digest_filename(week), f"digests/weekly/{digest_filename(week)}")

    for path in sorted(clusters_dir(data_dir).glob("*-clusters.json")):
        log = schemas.ClusterLog.model_validate_json(path.read_text(encoding="utf-8"))
        if not any(entry.week == week for cluster in log.clusters for entry in cluster.entries):
            continue
        (backup / "clusters").mkdir(exist_ok=True)
        shutil.copy2(path, backup / "clusters" / path.name)
        for cluster in log.clusters:
            cluster.entries = [entry for entry in cluster.entries if entry.week != week]
        log.clusters = [cluster for cluster in log.clusters if cluster.entries]
        path.write_text(log.model_dump_json(indent=2), encoding="utf-8")

    return backup


# --------------------------------------------------------------------------- #
# Digests
# --------------------------------------------------------------------------- #


def write_weekly_digest(week: str, markdown: str, data_dir: str | None = None) -> Path:
    """Write the weekly pulse digest (write-once).

    :param week: A week label such as ``"2026-W24"``.
    :param markdown: The digest markdown.
    :param data_dir: Optional workspace-root override.
    :returns: The written path.
    :raises WorkspaceError: If the digest already exists.
    """
    return write_once(weekly_digest_dir(data_dir) / digest_filename(week), markdown)


def read_weekly_digest(week: str, data_dir: str | None = None) -> str | None:
    """Read one week's pulse digest, if it was already composed.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: The digest markdown, or ``None`` when the week has no digest.
    """
    path = weekly_digest_dir(data_dir) / digest_filename(week)
    return path.read_text(encoding="utf-8") if path.exists() else None


def _sent_marker(digest_path: Path) -> Path:
    return digest_path.with_suffix(".sent.json")


def weekly_digest_sent(week: str, data_dir: str | None = None) -> bool:
    """Check whether a week's digest was already emailed.

    :param week: A week label such as ``"2026-W24"``.
    :param data_dir: Optional workspace-root override.
    :returns: ``True`` once the digest has a sent marker.
    """
    return _sent_marker(weekly_digest_dir(data_dir) / digest_filename(week)).exists()


def mark_weekly_digest_sent(week: str, message_id: str, data_dir: str | None = None) -> Path:
    """Record that a week's digest was emailed (write-once: a digest is sent once).

    :param week: A week label such as ``"2026-W24"``.
    :param message_id: The provider's id for the sent message.
    :param data_dir: Optional workspace-root override.
    :returns: The marker path.
    :raises WorkspaceError: If the digest was already marked sent.
    """
    marker = _sent_marker(weekly_digest_dir(data_dir) / digest_filename(week))
    return write_once(marker, json.dumps({"sent_at": datetime.now(UTC).isoformat(), "message_id": message_id}))


def monthly_digest_sent(month: str, data_dir: str | None = None) -> bool:
    """Check whether a month's digest was already emailed.

    :param month: A calendar month as ``"2026-07"``.
    :param data_dir: Optional workspace-root override.
    :returns: ``True`` once the digest has a sent marker.
    """
    return _sent_marker(monthly_digest_dir(data_dir) / monthly_digest_filename(month)).exists()


def mark_monthly_digest_sent(month: str, message_id: str, data_dir: str | None = None) -> Path:
    """Record that a month's digest was emailed (write-once).

    :param month: A calendar month as ``"2026-07"``.
    :param message_id: The provider's id for the sent message.
    :param data_dir: Optional workspace-root override.
    :returns: The marker path.
    :raises WorkspaceError: If the digest was already marked sent.
    """
    marker = _sent_marker(monthly_digest_dir(data_dir) / monthly_digest_filename(month))
    return write_once(marker, json.dumps({"sent_at": datetime.now(UTC).isoformat(), "message_id": message_id}))


def write_monthly_digest(month: str, markdown: str, data_dir: str | None = None) -> Path:
    """Write the monthly synthesis digest (write-once).

    :param month: A calendar month as ``"2026-07"``.
    :param markdown: The digest markdown.
    :param data_dir: Optional workspace-root override.
    :returns: The written path.
    :raises WorkspaceError: If the digest already exists.
    """
    return write_once(monthly_digest_dir(data_dir) / monthly_digest_filename(month), markdown)


def read_monthly_digest(month: str, data_dir: str | None = None) -> str | None:
    """Read one month's synthesis digest, if it was already composed.

    :param month: A calendar month as ``"2026-07"``.
    :param data_dir: Optional workspace-root override.
    :returns: The digest markdown, or ``None`` when the month has no digest.
    """
    path = monthly_digest_dir(data_dir) / monthly_digest_filename(month)
    return path.read_text(encoding="utf-8") if path.exists() else None


# --------------------------------------------------------------------------- #
# Human-owned config (read-only to agents)
# --------------------------------------------------------------------------- #


def config_dir(data_dir: str | None = None) -> Path:
    """Return the human-owned config directory.

    :param data_dir: Optional workspace-root override.
    :returns: The ``config`` directory as a ``Path``.
    """
    return _config_dir(data_dir)


def _config_dir(data_dir: str | None) -> Path:
    return workspace_root(data_dir) / "config"


def _read_config_yaml(filename: str, data_dir: str | None) -> str:
    """Read a human-owned config file from the workspace ``config/`` folder.

    The operator places ``themes.yaml`` and ``source-catalog.yaml`` in
    ``{HIPEAC_AGENTS_DATA_DIR}/config/``; agents read them and never edit them.

    :param filename: e.g. ``"themes.yaml"``.
    :param data_dir: Optional workspace-root override.
    :returns: The file content as text.
    :raises WorkspaceError: If the operator has not placed the file yet.
    """
    operator_copy = _config_dir(data_dir) / filename

    if not operator_copy.exists():
        raise WorkspaceError(
            f"missing human-owned config file: {operator_copy} — the operator must place and review it before running"
        )

    return operator_copy.read_text(encoding="utf-8")


def read_themes(data_dir: str | None = None) -> list[schemas.ThemeDef]:
    """Read the human-owned theme definitions.

    The digest order follows this file's order; agents never edit it.

    :param data_dir: Optional workspace-root override.
    :returns: The themes in config order.
    """
    parsed = yaml.safe_load(_read_config_yaml("themes.yaml", data_dir))
    return [schemas.ThemeDef.model_validate(theme) for theme in parsed["themes"]]


def read_source_catalog(data_dir: str | None = None) -> schemas.SourceCatalog:
    """Read the human-owned source catalog.

    :param data_dir: Optional workspace-root override.
    :returns: The parsed catalog.
    """
    parsed = yaml.safe_load(_read_config_yaml("source-catalog.yaml", data_dir))
    return schemas.SourceCatalog.model_validate(parsed)


__all__ = [
    "ClusterExistsError",
    "EntryAlreadyRecordedError",
    "WorkspaceError",
    "append_cluster",
    "append_cluster_entry",
    "cache_root",
    "cluster_filename",
    "clusters_dir",
    "create_cluster_log",
    "current_window",
    "digest_filename",
    "feed_snapshot_path",
    "findings_dir",
    "findings_path",
    "grouping_path",
    "list_weeks",
    "mark_monthly_digest_sent",
    "mark_weekly_digest_sent",
    "monthly_digest_sent",
    "purge_week",
    "monthly_digest_dir",
    "monthly_digest_filename",
    "read_all_findings",
    "read_cluster_log",
    "read_grouping_plan",
    "read_health_file",
    "read_sources_file",
    "read_feed_snapshot",
    "read_findings_file",
    "read_monthly_digest",
    "read_rejected_file",
    "read_weekly_digest",
    "read_source_catalog",
    "read_themes",
    "rejected_path",
    "weekly_digest_dir",
    "weekly_digest_sent",
    "weekly_label",
    "write_feed_snapshot",
    "week_cluster_entry_count",
    "week_dir",
    "workspace_root",
    "write_findings_file",
    "write_grouping_plan",
    "write_health",
    "write_sources_file",
    "write_rejected_file",
    "write_weekly_digest",
]
