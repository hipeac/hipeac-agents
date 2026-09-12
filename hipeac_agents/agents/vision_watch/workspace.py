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
"""

import re
from datetime import date
from pathlib import Path

import yaml

from hipeac_agents.agents.vision_watch import schemas, settings
from hipeac_agents.agents.vision_watch.cadence import current_window, weekly_label
from hipeac_agents.storage import WorkspaceError, write_once


_WEEK_LABEL = re.compile(r"\d{4}-W\d{2}")


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


def read_recent_findings(count: int = 2, data_dir: str | None = None) -> list[schemas.FindingsFile]:
    """Read the most recent findings files (for duplicate detection).

    :param count: How many recent weeks to read.
    :param data_dir: Optional workspace-root override.
    :returns: The parsed findings files, oldest first.
    """
    files = []

    for week in list_weeks(data_dir)[-count:]:
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


def _ensure_log_is_superset(existing: schemas.ClusterLog, proposed: schemas.ClusterLog) -> None:
    """Check a proposed cluster-log write only ever adds clusters and entries.

    :param existing: The log currently on disk.
    :param proposed: The log about to be written.
    :raises WorkspaceError: If an existing entry or cluster was edited or
        removed (append-only violation).
    """
    by_id = {cluster.id: cluster for cluster in existing.clusters}

    for cluster in proposed.clusters:
        prior = by_id.get(cluster.id)

        if prior is None:
            continue

        if cluster.name != prior.name or cluster.opened != prior.opened:
            raise WorkspaceError(f"cluster '{cluster.id}' header may not be edited")

        prior_ids = [entry.finding_id for entry in prior.entries]
        proposed_ids = [entry.finding_id for entry in cluster.entries]

        if len(proposed_ids) < len(prior_ids):
            raise WorkspaceError(f"cluster '{cluster.id}' entries may not be removed")

        for old_id, new_id in zip(prior_ids, proposed_ids, strict=True):
            if old_id != new_id:
                raise WorkspaceError(f"cluster '{cluster.id}' entries may not be reordered or edited")


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
    :raises WorkspaceError: If the cluster id already exists in the log.
    """
    path = clusters_dir(data_dir) / cluster_filename(theme)
    if path.exists():
        log = _read_cluster_log(theme, data_dir)
        if any(existing.id == cluster.id for existing in log.clusters):
            raise WorkspaceError(f"cluster '{cluster.id}' already exists in theme '{theme}'")
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
    :raises WorkspaceError: If the log or cluster does not exist, or the
        finding is already recorded in it.
    """
    log = _read_cluster_log(theme, data_dir)
    cluster = next((c for c in log.clusters if c.id == cluster_id), None)

    if cluster is None:
        raise WorkspaceError(f"cluster '{cluster_id}' does not exist in theme '{theme}'")

    if any(existing.finding_id == entry.finding_id for existing in cluster.entries):
        raise WorkspaceError(f"finding '{entry.finding_id}' already in cluster '{cluster_id}'")
    if any(existing.url == entry.url for existing in cluster.entries):
        raise WorkspaceError(f"url '{entry.url}' already in cluster '{cluster_id}'")

    cluster.entries.append(entry)
    (clusters_dir(data_dir) / cluster_filename(theme)).write_text(log.model_dump_json(indent=2), encoding="utf-8")


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


def read_latest_weekly_digest(data_dir: str | None = None) -> str | None:
    """Read the most recent weekly digest, for "last digest" context.

    :param data_dir: Optional workspace-root override.
    :returns: The latest digest markdown, or ``None`` if none exists.
    """
    digests = sorted(weekly_digest_dir(data_dir).glob("digest-*.md"))
    return digests[-1].read_text(encoding="utf-8") if digests else None


def write_monthly_digest(month: str, markdown: str, data_dir: str | None = None) -> Path:
    """Write the monthly synthesis digest (write-once).

    :param month: A calendar month as ``"2026-07"``.
    :param markdown: The digest markdown.
    :param data_dir: Optional workspace-root override.
    :returns: The written path.
    :raises WorkspaceError: If the digest already exists.
    """
    return write_once(monthly_digest_dir(data_dir) / monthly_digest_filename(month), markdown)


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
    "WorkspaceError",
    "append_cluster",
    "append_cluster_entry",
    "cache_root",
    "cluster_filename",
    "clusters_dir",
    "create_cluster_log",
    "current_window",
    "digest_filename",
    "findings_dir",
    "findings_path",
    "grouping_path",
    "list_weeks",
    "monthly_digest_dir",
    "monthly_digest_filename",
    "read_all_findings",
    "read_cluster_log",
    "read_grouping_plan",
    "read_findings_file",
    "read_latest_weekly_digest",
    "read_recent_findings",
    "read_rejected_file",
    "read_source_catalog",
    "read_themes",
    "rejected_path",
    "weekly_digest_dir",
    "weekly_label",
    "week_dir",
    "workspace_root",
    "write_findings_file",
    "write_grouping_plan",
    "write_rejected_file",
    "write_weekly_digest",
]
