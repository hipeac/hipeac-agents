"""The harvest node's orchestration: channels, integration, file writes.

``harvest_node`` runs the channel functions from ``channels.py``, folds
near-matches, re-samples, and writes the two write-once evidence files
through the storage layer.
"""

import asyncio
import logging
from datetime import date
from typing import Any

from hipeac_agents.agents.vision_watch import settings as watch_settings
from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.schemas import Finding, FindingsFile, RejectedFile, RejectedItem
from hipeac_agents.agents.vision_watch.state import SourceOutcome, VisionWatchState
from hipeac_agents.services.factory import Services

from .channels import (
    _window_end_dt,
    _window_start_dt,
    attribute_messages,
    harvest_board_tips,
    harvest_feed_source,
    harvest_inbox_unattributed,
    harvest_newsletter_source,
    harvest_sweep,
    harvest_web_source,
)
from .context import HarvestContext
from .gates import build_due_list, dedupe_rejects, find_id, kept_findings, pick_resample


logger = logging.getLogger(__name__)


async def harvest_node(
    state: VisionWatchState,
    *,
    services: Services,
    llm: Any,
) -> dict[str, Any]:
    """Run one weekly harvest: collect, verify, record; write the two files.

    :param state: The graph state; carries the week window.
    :param services: The wired service clients (crawl required; mail optional).
    :param llm: The chat model used for the flagged judgement calls.
    :returns: State updates: findings, rejected items, source outcomes.
    """
    # Preflight: the evidence files are write-once, so a week already
    # harvested would scrape and judge everything again only to raise on the
    # final write. Replay the recorded evidence instead, for free.
    if recorded := workspace.read_findings_file(state.week):
        logger.info("week %s already harvested; replaying recorded evidence", state.week)
        rejected_file = workspace.read_rejected_file(state.week)
        return {
            "findings": recorded.findings,
            "rejected": rejected_file.rejected if rejected_file else [],
            "source_outcomes": [
                SourceOutcome(source_id="harvest", status="skipped", detail=f"{state.week} already harvested")
            ],
        }

    # Finding ids are reused when a week is harvested again, so entries left
    # from an earlier harvest would point at different findings. Refuse
    # before spending anything; ``--redo`` sets the week aside properly.
    if stale := workspace.week_cluster_entry_count(state.week):
        raise workspace.WorkspaceError(
            f"week {state.week} still has {stale} cluster entries from an earlier harvest; rerun with --redo"
        )

    ctx = HarvestContext(llm)
    window_start = state.window_start or date.today()
    window_end = state.window_end or window_start
    themes = workspace.read_themes()
    catalog = workspace.read_source_catalog()
    prior = workspace.read_all_findings()

    outcomes: list[SourceOutcome] = []
    verified: list[Finding] = []
    rejected: list[RejectedItem] = []
    due_list = build_due_list(catalog)

    if state.source_only:
        due_list = [s for s in due_list if s.id in set(state.source_only)]

    if state.source_limit is not None:
        due_list = due_list[: state.source_limit]

    if services.crawl is None:
        for source in due_list:
            outcomes.append(SourceOutcome(source_id=source.id, status="failed", detail="crawl service not configured"))
        return {"source_outcomes": outcomes, "rejected": [], "findings": []}

    # web channel.
    # Web channel: bounded concurrency — a hundred sources firing scrapes
    # and LLM calls at once trips the provider rate limits.
    source_slots = asyncio.Semaphore(8)

    async def _bounded(coro, source):
        async with source_slots:
            return await coro

    web_sources = [s for s in due_list if s.web]
    web_results = await asyncio.gather(
        *(
            _bounded(
                # Sources with a feed go through the deterministic feed channel
                # (plain GET + feedparser, no Firecrawl, no extraction call);
                # the rest through page scraping + extraction.
                harvest_feed_source(ctx, services, s, window_start, window_end, prior, themes)
                if s.feed_url
                else harvest_web_source(ctx, services, s, window_start, window_end, prior, themes),
                s,
            )
            for s in web_sources
        ),
        return_exceptions=True,
    )

    # Newsletter + board-tip channels: one inbox read, attributed once.
    newsletter_sources = [s for s in due_list if s.newsletter]
    inbox_messages: list = []
    if services.mail is not None and watch_settings.AGENTMAIL_INBOX_VISION_WATCH:
        inbox_messages = await services.mail.list_messages(
            watch_settings.AGENTMAIL_INBOX_VISION_WATCH,
            after=_window_start_dt(window_start),
            before=_window_end_dt(window_end),
        )
    attributed, tips_messages, unattributed = attribute_messages(
        inbox_messages, newsletter_sources, watch_settings.HIPEAC_VISION_TIPS_MAILBOX
    )
    newsletter_results = await asyncio.gather(
        *(
            _bounded(
                harvest_newsletter_source(ctx, services, s, attributed[s.id], window_start, window_end, prior, themes),
                s,
            )
            for s in newsletter_sources
        ),
        return_exceptions=True,
    )
    inbox_result = await harvest_inbox_unattributed(
        ctx, services, unattributed, window_start, window_end, prior, themes
    )

    # Board tips.
    tips = await harvest_board_tips(ctx, services, tips_messages, window_start, window_end, prior, themes)

    # The general sweep.
    if state.skip_sweep:
        sweep = ([], [], SourceOutcome(source_id="sweep", status="skipped", detail="--skip-sweep"))
    else:
        sweep = await harvest_sweep(ctx, services, themes, window_start, window_end, prior)

    channel_ids = [s.id for s in web_sources] + [s.id for s in newsletter_sources] + ["inbox", "board-tip", "sweep"]
    for source_id, result in zip(
        channel_ids, (*web_results, *newsletter_results, inbox_result, tips, sweep), strict=True
    ):
        if isinstance(result, BaseException):
            outcomes.append(SourceOutcome(source_id=source_id, status="failed", detail=repr(result)))
            continue
        verified.extend(result[0])
        rejected.extend(result[1])
        outcomes.append(result[2])
        logger.info(
            "source %s: %s (%dv/%dr)",
            result[2].source_id,
            result[2].status,
            result[2].verified,
            result[2].rejected,
        )

    # Integration: URL dedupe, near-match fold, re-sample, write.
    capped, capped_rejects = _cap_source_volume(verified)

    merged = _merge_url_duplicates(capped)
    numbered = _assign_ids(state.week, merged)
    numbered, folded_rejects = await _fold_near_matches(ctx, numbered)
    numbered = await _resample(services.crawl, numbered, rejected)

    findings_file = FindingsFile(week=state.week, created=date.today(), findings=numbered)
    rejected_file = RejectedFile(
        week=state.week,
        created=date.today(),
        rejected=dedupe_rejects(rejected + capped_rejects + folded_rejects),
    )
    workspace.write_findings_file(findings_file)
    workspace.write_rejected_file(rejected_file)

    return {
        "findings": numbered,
        "rejected": rejected_file.rejected,
        "source_outcomes": outcomes,
    }


def _assign_ids(week: str, findings: list[Finding]) -> list[Finding]:
    """Assign sequential finding ids for the week.

    :param week: The week label.
    :param findings: The verified findings, in collection order.
    :returns: The findings with ids like ``f-2026-W24-01``.
    """
    return [
        finding.model_copy(update={"id": find_id(week, ordinal)}) for ordinal, finding in enumerate(findings, start=1)
    ]


def _join_corroboration(*parts: str | None) -> str | None:
    """Join corroboration fragments, dropping the empty ones.

    :param parts: The fragments to join, in order.
    :returns: The joined corroboration, or ``None`` when nothing was given.
    """
    return "; ".join(filter(None, parts)) or None


# Weekly bounds on recorded findings per source, one criterion for every
# source. High-volume feeds (arXiv category feeds, aggregators, newsletters)
# can pass dozens of in-window candidates a day — every one trivially
# on-theme by title and abstract — which floods clusters and inflates the
# finding counts the trend thresholds rely on. Each source keeps its gate
# call's genuinely significant developments, bounded 2-4, audited otherwise.
_SOURCE_KEEP_MIN = 2
_SOURCE_KEEP_MAX = 4
_SOURCE_SIGNIFICANCE_FLOOR = 4


def _cap_source_volume(
    findings: list[Finding],
) -> tuple[list[Finding], list[RejectedItem]]:
    """Cap every source at its most significant findings of the week.

    A source keeps every development the gate call scored
    ``significance >= 4``, bounded to 2-4 per source: fewer than the floor
    qualifying keeps the top ranked developments anyway (a quiet week still
    records something), more than the ceiling trims to the strongest.
    Selection is deterministic over a judgement recorded once at gate time;
    the dropped developments move to the rejected audit with reason
    ``source_cap``, so nothing is lost silently.

    :param findings: The verified findings from all channels.
    :returns: ``(capped findings, rejected overflow items)``.
    """
    capped: list[Finding] = []
    overflow: list[RejectedItem] = []

    by_source: dict[str, list[Finding]] = {}
    for finding in findings:
        by_source.setdefault(finding.source_id, []).append(finding)

    for group in by_source.values():
        if len(group) <= _SOURCE_KEEP_MAX:
            capped.extend(group)
            continue

        group.sort(key=lambda f: (-f.significance, f.tier, -f.date.toordinal()))
        keep = [f for f in group if f.significance >= _SOURCE_SIGNIFICANCE_FLOOR]
        if len(keep) < _SOURCE_KEEP_MIN:
            keep = group[:_SOURCE_KEEP_MIN]
        keep = keep[:_SOURCE_KEEP_MAX]
        capped.extend(keep)

        kept_urls = {f.url for f in keep}
        for finding in group:
            if finding.url not in kept_urls:
                overflow.append(
                    RejectedItem(
                        url=finding.url,
                        claimed_title=finding.title,
                        source_id=finding.source_id,
                        reason="source_cap",
                        detail=(
                            f"source volume cap: kept {len(keep)} of {len(group)} "
                            f"(significance floor {_SOURCE_SIGNIFICANCE_FLOOR}, "
                            f"bounded {_SOURCE_KEEP_MIN}-{_SOURCE_KEEP_MAX})"
                        ),
                        summary=finding.summary,
                    )
                )

    return capped, overflow


def _merge_url_duplicates(findings: list[Finding]) -> list[Finding]:
    """Fold findings that share a URL — one development, one finding.

    The LLM near-match rule handles the same event under a different URL; an
    identical URL needs no judgement call. The best (lowest-tier) finding is
    kept and the rest fold into its ``corroboration``, preserving order.

    :param findings: The verified findings.
    :returns: The merged findings, first-seen order preserved.
    """
    by_url: dict[str, Finding] = {}
    order: list[str] = []
    folded: dict[str, list[str]] = {}

    for finding in findings:
        primary = by_url.get(finding.url)

        if primary is None:
            by_url[finding.url] = finding
            order.append(finding.url)
            continue

        if (finding.tier, finding.datapoint) < (primary.tier, primary.datapoint):
            folded.setdefault(finding.url, []).append(primary.summary)
            # The displaced primary's corroboration is evidence too: keep the
            # winner's own and inherit the primary's, rather than overwriting.
            by_url[finding.url] = finding.model_copy(
                update={"corroboration": _join_corroboration(finding.corroboration, primary.corroboration)}
            )
            continue

        folded.setdefault(finding.url, []).append(finding.summary)

    merged = []

    for url in order:
        finding = by_url[url]
        extras = folded.get(url)

        if extras:
            finding = finding.model_copy(update={"corroboration": _join_corroboration(finding.corroboration, *extras)})

        merged.append(finding)

    return merged


async def _fold_near_matches(ctx: HarvestContext, findings: list[Finding]) -> tuple[list[Finding], list[RejectedItem]]:
    """Fold near-matched findings into their strongest verification.

    LLM judgement call (near-match rule) — see ``prompts.NEAR_MATCH``.

    :param ctx: The harvest context holding the LLM runners.
    :param findings: The verified findings with sequential ids.
    :returns: The surviving findings, plus one ``duplicate`` reject per folded item.
    """
    if len(findings) < 2:
        return findings, []
    by_id = {f.id: f for f in findings}
    groups = []
    # Batched: a full week's findings can exceed what one call groups well.
    for chunk in range(0, len(findings), 50):
        batch = findings[chunk : chunk + 50]
        groups.extend((await ctx.near_match_groups([(f.id, f.title) for f in batch])).groups)
    drop: set[str] = set()

    for group in groups:
        members = [by_id[fid] for fid in group if fid in by_id]
        if len(members) < 2:
            continue
        members.sort(key=lambda f: f.tier)
        primary = members[0]
        primary.corroboration = _join_corroboration(primary.corroboration, *(m.summary for m in members[1:]))
        drop.update(m.id for m in members[1:])

    folded = [
        RejectedItem(
            url=by_id[fid].url,
            claimed_title=by_id[fid].title,
            source_id=by_id[fid].source_id,
            reason="duplicate",
            detail="same underlying event as another finding (near-match rule)",
        )
        for fid in drop
    ]

    return kept_findings(findings, drop), folded


async def _resample(crawl: Any, findings: list[Finding], rejected: list[RejectedItem]) -> list[Finding]:
    """Re-sample ~20% of findings with a fresh fetch; move failures to rejected.

    A finding whose URL no longer resolves is *moved*, not copied: it is
    appended to the rejected audit and dropped from the findings, so the two
    write-once files never disagree about it.

    :param crawl: The crawl client.
    :param findings: The verified findings.
    :param rejected: The rejected list to append failures to.
    :returns: The findings minus the ones that failed re-sampling.
    """
    sample = pick_resample(findings)
    # A provider error (credits ran out, timeout) says nothing about the link:
    # keep the finding rather than lose the whole week's work at the last step.
    fetched = await asyncio.gather(*(crawl.scrape(f.url, fresh=True) for f in sample), return_exceptions=True)
    drop: set[str] = set()

    for finding, result in zip(sample, fetched, strict=True):
        if isinstance(result, BaseException):
            logger.warning("re-sample of %s skipped: %r", finding.url, result)
            continue
        if result is None:
            rejected.append(
                RejectedItem(
                    url=finding.url, claimed_title=finding.title, source_id=finding.source_id, reason="url_404"
                )
            )
            drop.add(finding.id)

    return kept_findings(findings, drop)
