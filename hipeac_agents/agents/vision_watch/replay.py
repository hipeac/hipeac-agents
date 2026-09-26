"""Offline replay of the forward-looking gate over recorded weeks.

Past weeks cannot be harvested again — feeds move on — but every candidate
the old gate saw is on disk: findings, and rejects with their title and
summary. The replay runs the current triage and verdict over them, using
cached page titles instead of scraping, and writes the result beside the
live workspace for review. ``apply_replay`` then swaps it in: the old
evidence and clusters are archived as ``-v1`` and the weeks re-clustered.
"""

import math
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.harvest import node as harvest_node
from hipeac_agents.agents.vision_watch.nodes.harvest.channels import gate_candidates
from hipeac_agents.agents.vision_watch.nodes.harvest.context import TRIAGE_BATCH, HarvestContext
from hipeac_agents.agents.vision_watch.nodes.harvest.models import CandidateItem
from hipeac_agents.agents.vision_watch.schemas import (
    Finding,
    FindingsFile,
    RejectedFile,
    RejectedItem,
    SourceCatalog,
    ThemeDef,
)
from hipeac_agents.services.factory import Services
from hipeac_agents.services.types import ScrapeResult
from hipeac_agents.services.urls import normalize_url
from hipeac_agents.storage import cache as json_cache


# Only candidates the old gate judged on relevance are worth re-judging;
# window, duplicate, dead-link and title failures stay what they were.
REPLAYED_REASONS = {"off_theme", "source_cap"}
NON_CATALOG = {"sweep": "sweep", "inbox": "newsletter", "board-tip": "board-tip"}


@dataclass(frozen=True)
class RecordedCandidate:
    """One candidate as the old gate left it on disk."""

    source_id: str
    candidate: CandidateItem
    was: str  # "finding", or the old rejection reason


def week_window(week: str) -> tuple[date, date]:
    """Return the Saturday–Friday window a week label names.

    :param week: A week label such as ``"2026-W39"``.
    :returns: ``(saturday, friday)``.
    """
    year, number = week.split("-W")
    friday = date.fromisocalendar(int(year), int(number), 5)
    return friday - timedelta(days=6), friday


def weeks_between(first: str, last: str) -> list[str]:
    """List the recorded weeks from ``first`` to ``last`` inclusive.

    :param first: The first week label.
    :param last: The last week label.
    :returns: The recorded week labels in range, oldest first.
    """
    return [week for week in workspace.list_weeks() if first <= week <= last]


def recorded_candidates(week: str) -> tuple[list[RecordedCandidate], list[RejectedItem]]:
    """Read what a week's old gate saw.

    Rejects carry no date; they passed the window check when first seen, so
    they are dated the week's Friday, as the old gate recorded undated items.

    :param week: The week label.
    :returns: ``(candidates to replay, rejects kept as they were)``.
    """
    findings_file = workspace.read_findings_file(week)
    rejected_file = workspace.read_rejected_file(week)
    friday = week_window(week)[1].isoformat()

    replay = [
        RecordedCandidate(
            f.source_id,
            CandidateItem(title=f.title, url=f.url, date=f.date.isoformat(), summary=f.summary, datapoint=f.datapoint),
            "finding",
        )
        for f in (findings_file.findings if findings_file else [])
    ]
    kept: list[RejectedItem] = []
    for item in rejected_file.rejected if rejected_file else []:
        if item.reason in REPLAYED_REASONS:
            replay.append(
                RecordedCandidate(
                    item.source_id,
                    CandidateItem(title=item.claimed_title, url=item.url, date=friday, summary=item.summary),
                    item.reason,
                )
            )
        else:
            kept.append(item)
    return replay, kept


def plan_calls(candidates_by_week: dict[str, list[RecordedCandidate]]) -> dict[str, int]:
    """Estimate the judgement calls a replay would make, before spending anything.

    :param candidates_by_week: The recorded candidates per week.
    :returns: Counts: weeks, candidates, triage calls, at most this many verdicts, near-match calls.
    """
    triage = verdicts = near = 0
    for candidates in candidates_by_week.values():
        by_source: dict[str, int] = {}
        for c in candidates:
            by_source[c.source_id] = by_source.get(c.source_id, 0) + 1
        triage += sum(math.ceil(n / TRIAGE_BATCH) for source, n in by_source.items() if source != "board-tip")
        verdicts += len(candidates)
        near += math.ceil(len(candidates) / 50)
    return {
        "weeks": len(candidates_by_week),
        "candidates": sum(len(c) for c in candidates_by_week.values()),
        "triage_calls": triage,
        "max_verdict_calls": verdicts,
        "max_near_match_calls": near,
    }


def _known_page(candidate: CandidateItem) -> ScrapeResult:
    """Use the cached scrape of a candidate's page, or its own title when never scraped.

    :param candidate: The recorded candidate.
    :returns: The page to judge the title against.
    """
    path = json_cache.sharded_path(workspace.cache_root(), "scrapes", normalize_url(candidate.url))
    cached = json_cache.cache_get(path)
    if cached:
        return ScrapeResult.model_validate(cached["payload"])
    return ScrapeResult(url=candidate.url, title=candidate.title, markdown=candidate.summary)


async def replay_week(
    ctx: HarvestContext, week: str, themes: list[ThemeDef], catalog: SourceCatalog
) -> tuple[FindingsFile, RejectedFile, list[RecordedCandidate]]:
    """Run the current gate over one recorded week.

    :param ctx: The harvest context holding the LLM runners.
    :param week: The week label.
    :param themes: The watch questions.
    :param catalog: The source catalog.
    :returns: ``(new findings, new rejected, the replayed candidates)``.
    """
    candidates, kept_rejects = recorded_candidates(week)
    window_start, window_end = week_window(week)
    sources = {s.id: s for s in catalog.sources}
    services = Services(crawl=None, mail=None, vision=None)

    by_source: dict[str, list[CandidateItem]] = {}
    for c in candidates:
        by_source.setdefault(c.source_id, []).append(c.candidate)

    verified: list[Finding] = []
    rejected: list[RejectedItem] = list(kept_rejects)
    for source_id, items in by_source.items():
        source = sources.get(source_id)
        findings, rejects = await gate_candidates(
            ctx,
            services,
            items,
            source,
            window_start,
            window_end,
            [],
            themes,
            source_id,
            "direct" if source else NON_CATALOG.get(source_id, "sweep"),
            tip=source_id == "board-tip",
            known_pages={item.url: _known_page(item) for item in items},
        )
        verified.extend(findings)
        rejected.extend(rejects)

    capped, overflow = harvest_node._cap_source_volume(verified)
    numbered = harvest_node._assign_ids(week, harvest_node._merge_url_duplicates(capped))
    numbered, folded = await harvest_node._fold_near_matches(ctx, numbered)
    today = date.today()
    return (
        FindingsFile(week=week, created=today, generated_by="replay-gate", findings=numbered),
        RejectedFile(
            week=week,
            created=today,
            generated_by="replay-gate",
            rejected=harvest_node.dedupe_rejects(rejected + overflow + folded),
        ),
        candidates,
    )


def render_report(
    results: list[tuple[str, FindingsFile, list[RecordedCandidate]]], themes: list[ThemeDef], calls: dict[str, int]
) -> str:
    """Render the review report: what the new gate keeps that the old one dropped, and the reverse.

    :param results: Per week: its label, the new findings, and the replayed candidates.
    :param themes: The watch questions.
    :param calls: The planned call counts.
    :returns: The report markdown.
    """
    lines = ["# replay-gate report", "", f"Planned calls: {calls}", ""]
    per_question: dict[str, int] = {t.theme: 0 for t in themes}
    total_new = total_dropped = 0
    body: list[str] = []

    for week, findings_file, candidates in results:
        new_urls = {normalize_url(f.url) for f in findings_file.findings}
        old_findings = [c for c in candidates if c.was == "finding"]
        gained = [
            f
            for f in findings_file.findings
            if normalize_url(f.url) not in {normalize_url(c.candidate.url) for c in old_findings}
        ]
        dropped = [c for c in old_findings if normalize_url(c.candidate.url) not in new_urls]
        for f in findings_file.findings:
            for theme_id in f.theme_ids:
                per_question[theme_id] = per_question.get(theme_id, 0) + 1
        total_new += len(gained)
        total_dropped += len(dropped)

        body.extend(
            [
                f"## {week}: {len(findings_file.findings)} findings (was {len(old_findings)}), "
                f"+{len(gained)} gained, -{len(dropped)} dropped",
                "",
            ]
        )
        body.extend(
            f"- **+** [{', '.join(f.theme_ids)}] {f.title} ({f.source_id}, sig {f.significance}, {f.horizon or '?'})"
            + (f" — {f.forward_note}" if f.forward_note else "")
            for f in gained
        )
        body.extend(f"- **−** {c.candidate.title} ({c.source_id})" for c in dropped)
        body.append("")

    lines.extend(
        [
            f"Across {len(results)} weeks: +{total_new} findings gained, -{total_dropped} dropped.",
            "",
            "Findings per watch question: " + ", ".join(f"{k} {v}" for k, v in per_question.items()),
            "",
        ]
    )
    return "\n".join(lines + body)


def write_replay(results: list[tuple[str, FindingsFile, RejectedFile]], report: str, name: str) -> Path:
    """Write a replay's evidence and report beside the live workspace.

    :param results: Per week: its label, new findings, new rejected.
    :param report: The review report.
    :param name: The replay's folder name.
    :returns: The replay folder.
    """
    root = workspace.workspace_root() / "replay" / f"{name}-{datetime.now(UTC):%Y%m%dT%H%M%S}"
    for week, findings_file, rejected_file in results:
        folder = root / "evidence" / week
        folder.mkdir(parents=True)
        (folder / "findings.json").write_text(findings_file.model_dump_json(indent=2), encoding="utf-8")
        (folder / "rejected.json").write_text(rejected_file.model_dump_json(indent=2), encoding="utf-8")
    (root / "report.md").write_text(report, encoding="utf-8")
    return root


def install_replay(replay_dir: Path) -> list[str]:
    """Swap a reviewed replay into the live workspace (the cutover).

    Archives ``evidence/`` and ``clusters/`` as ``evidence-v1/`` and
    ``clusters-v1/``, installs the replayed weeks' findings and rejects,
    carries over each week's source report and health files, and copies
    weeks outside the replay as they were. Clusters start empty: the caller
    re-clusters the returned weeks in order.

    :param replay_dir: A folder written by ``write_replay``.
    :returns: The replayed weeks, oldest first, to re-cluster.
    :raises FileExistsError: If a ``-v1`` archive already exists.
    """
    root = workspace.workspace_root()
    evidence, clusters = root / "evidence", root / "clusters"
    evidence_v1, clusters_v1 = root / "evidence-v1", root / "clusters-v1"
    for archive in (evidence_v1, clusters_v1):
        if archive.exists():
            raise FileExistsError(f"{archive} already exists; a replay was already installed")

    shutil.move(evidence, evidence_v1)
    if clusters.exists():
        shutil.move(clusters, clusters_v1)

    replayed = sorted(p.name for p in (replay_dir / "evidence").iterdir() if p.is_dir())
    for old_week in sorted(p for p in evidence_v1.iterdir() if p.is_dir()):
        target = evidence / old_week.name
        if old_week.name not in replayed:
            shutil.copytree(old_week, target)
            continue
        target.mkdir(parents=True)
        for name in ("findings.json", "rejected.json"):
            shutil.copy2(replay_dir / "evidence" / old_week.name / name, target / name)
        for name in ("sources.json", "health.json", "health.md"):
            if (old_week / name).exists():
                shutil.copy2(old_week / name, target / name)
    return replayed


__all__ = [
    "install_replay",
    "plan_calls",
    "recorded_candidates",
    "render_report",
    "replay_week",
    "week_window",
    "weeks_between",
    "write_replay",
]
