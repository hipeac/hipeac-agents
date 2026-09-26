"""The harvest node's channels: one function per collection channel.

Channels: feeds, arXiv, scraped pages, newsletters, the unattributed inbox,
board tips, and the general sweep (one date-bounded web search per watch
question). The gate (``gate_candidates``) is shared by all of them.
"""

import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from html import unescape
from typing import Any

from hipeac_agents.agents.vision_watch import schemas
from hipeac_agents.agents.vision_watch import settings as watch_settings
from hipeac_agents.agents.vision_watch.schemas import Finding, FindingsFile, RejectedItem
from hipeac_agents.agents.vision_watch.state import SourceOutcome
from hipeac_agents.services.factory import Services
from hipeac_agents.services.types import ScrapeResult
from hipeac_agents.services.urls import normalize_url

from .context import HarvestContext
from .gates import (
    cap_tier,
    duplicate_gate,
    extract_links,
    headline_in_body,
    http_url_is_dead,
    parse_iso_date,
    window_gate,
)
from .models import CandidateItem


logger = logging.getLogger(__name__)


def _days_outside(item_date: date, window_start: date, window_end: date) -> int:
    """Days a date falls outside the harvest window (0 when inside).

    :param item_date: The item's publication date.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :returns: Distance in days; 0 when inside the window.
    """
    if window_start <= item_date <= window_end:
        return 0
    return (window_start - item_date).days if item_date < window_start else (item_date - window_end).days


def _reject(candidate: Any, source_id: str, reason: str, detail: str = "") -> RejectedItem:
    """Build a rejected item from a failed candidate.

    :param candidate: The candidate that failed a gate.
    :param source_id: The source the candidate came from.
    :param reason: One of the documented rejection reasons.
    :param detail: Optional extra detail for the audit file.
    :returns: The rejected item.
    """
    return RejectedItem(
        url=candidate.url,
        claimed_title=candidate.title,
        source_id=source_id,
        reason=reason,
        detail=detail,
        summary=candidate.summary,
    )


def _pre_gate(
    candidate: CandidateItem, source_id: str, window_start: date, window_end: date, prior: list[FindingsFile]
) -> RejectedItem | None:
    """Run the free checks before any judgement or scrape: window, then duplicate.

    :param candidate: The candidate.
    :param source_id: The source it came from.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :param prior: All recorded findings files, for duplicate detection.
    :returns: The rejection, or ``None`` when the candidate passes.
    """
    item_date = parse_iso_date(candidate.date) or parse_iso_date(candidate.summary)

    if not window_gate(item_date, window_start, window_end):
        days_out = _days_outside(item_date, window_start, window_end)
        detail = f"near_window ({days_out}d outside) published {item_date.isoformat()}" if days_out <= 7 else ""
        return _reject(candidate, source_id, "out_of_window", detail)

    if duplicate_gate(candidate.url, prior):
        return _reject(candidate, source_id, "duplicate")

    return None


async def gate_candidates(
    ctx: HarvestContext,
    services: Services,
    candidates: list[CandidateItem],
    source: schemas.SourceEntry | None,
    window_start: date,
    window_end: date,
    prior: list[FindingsFile],
    themes: list[schemas.ThemeDef],
    fallback_source_id: str,
    access_method: str,
    *,
    tip: bool = False,
    triaged: bool = False,
    known_pages: dict[str, ScrapeResult] | None = None,
) -> tuple[list[Finding], list[RejectedItem]]:
    """Gate one source's candidates: free checks, one triage call, then verification.

    Order is cheapest first: window and duplicate cost nothing; one batched
    triage call per source decides which candidates could move a watch
    question; only those are scraped and get the full verdict. Gate failures
    never drop silently: every reject carries its reason.

    :param candidates: The source's candidates.
    :param source: The catalog source they came from, if any.
    :param fallback_source_id: ``"sweep"``, ``"inbox"`` or ``"board-tip"`` for non-catalog items.
    :param access_method: e.g. ``"direct"``, ``"firecrawl"``, ``"newsletter"``.
    :param tip: Board tip: an editor flagged it, so triage and the title,
        date and roundup checks step aside, and the verdict must name the
        closest question.
    :param triaged: The candidates already passed triage (the sweep triages its hits).
    :param known_pages: Pages a structured source already carries (arXiv), by URL.
    :returns: ``(verified_findings, rejected_items)``.
    """
    source_id = source.id if source else fallback_source_id
    rejected: list[RejectedItem] = []
    survivors: list[CandidateItem] = []

    for candidate in candidates:
        if reject := _pre_gate(candidate, source_id, window_start, window_end, prior):
            rejected.append(reject)
        else:
            survivors.append(candidate)

    if survivors and not (tip or triaged):
        kept = await ctx.triage([(c.title, c.summary) for c in survivors], themes)
        rejected.extend(
            _reject(c, source_id, "off_theme", "triage: moves no watch question")
            for i, c in enumerate(survivors)
            if i not in kept
        )
        survivors = [c for i, c in enumerate(survivors) if i in kept]

    verified: list[Finding] = []
    for candidate in survivors:
        finding, reject = await _verify_candidate(
            ctx,
            services,
            candidate,
            source,
            window_start,
            window_end,
            themes,
            source_id,
            access_method,
            tip,
            (known_pages or {}).get(candidate.url),
        )
        if finding:
            verified.append(finding)
        if reject:
            rejected.append(reject)

    return verified, rejected


async def _verify_candidate(
    ctx: HarvestContext,
    services: Services,
    candidate: CandidateItem,
    source: schemas.SourceEntry | None,
    window_start: date,
    window_end: date,
    themes: list[schemas.ThemeDef],
    source_id: str,
    access_method: str,
    tip: bool,
    known_page: ScrapeResult | None,
) -> tuple[Finding | None, RejectedItem | None]:
    """Verify one triaged candidate: liveness, scrape, date, forward-looking verdict.

    :param known_page: The item's page when a structured source already
        carries it (arXiv): no liveness check and no scrape are needed.
    :returns: ``(finding, None)`` when verified, ``(None, reject)`` otherwise.
    """
    item_date = parse_iso_date(candidate.date) or parse_iso_date(candidate.summary)

    if known_page is None and http_url_is_dead(candidate.url):
        return None, _reject(candidate, source_id, "url_404")

    page = known_page or await services.crawl.scrape(candidate.url)

    if page is None:
        return None, _reject(candidate, source_id, "url_404")

    if item_date is None:
        item_date = parse_iso_date(page.published_at or "")
        if item_date and not window_gate(item_date, window_start, window_end):
            days_out = _days_outside(item_date, window_start, window_end)
            detail = f"near_window ({days_out}d outside) published {item_date.isoformat()}" if days_out <= 7 else ""
            return None, _reject(candidate, source_id, "out_of_window", detail)

    # An item with no date anywhere may be years old (an evergreen page, an
    # archive link): it cannot be presented as this week's news.
    if item_date is None and not tip:
        return None, _reject(candidate, source_id, "undated", "no date in the source, the text or the page")

    verdict = await ctx.gate_candidate(candidate.title, candidate.summary, page.title, themes, tip=tip)

    if not verdict.title_matches and not tip:
        return None, _reject(candidate, source_id, "title_mismatch", verdict.title_detail)

    if verdict.is_roundup and not tip:
        return None, _reject(candidate, source_id, "roundup", "a digest of many items, not one development")

    theme_ids = [theme_id for theme_id in verdict.theme_ids if theme_id in {t.theme for t in themes}]
    if not theme_ids and not tip:
        return None, _reject(candidate, source_id, "off_theme")

    return (
        Finding(
            id="",
            date=item_date or window_end,
            title=candidate.title,
            url=page.url or candidate.url,
            source_id=source_id,
            region=source.region if source else "global",
            tier=cap_tier(verdict.tier, source.tier if source else 4),
            theme_ids=theme_ids,
            datapoint=verdict.datapoint or candidate.datapoint,
            summary=verdict.summary or candidate.summary or verdict.title_detail,
            significance=verdict.significance,
            access_method=access_method,
            direction=verdict.direction,
            horizon=verdict.horizon,
            forward_note=verdict.forward_note,
        ),
        None,
    )


def _dated_by_message(candidate: CandidateItem, message: Any) -> CandidateItem:
    """Date an undated newsletter item by its message: the email itself is in-window evidence.

    :param candidate: The candidate extracted from the message.
    :param message: The inbox message it came from.
    :returns: The candidate, dated when it had no date.
    """
    stamp = getattr(message, "timestamp", None) or getattr(message, "created_at", None)
    if candidate.date or stamp is None:
        return candidate
    return candidate.model_copy(update={"date": stamp.date().isoformat()})


_FEED_MARKUP = re.compile(r"<[^>]+>")
_FEED_PREAMBLE = re.compile(r"^(?:arxiv:\S+\s*)?announce type:\s*\S+\s*(?:abstract:\s*)?", re.IGNORECASE)
_ABSTRACT_LEAD = re.compile(r"^abstract:\s*", re.IGNORECASE)


def _clean_feed_summary(raw: str) -> str:
    """Normalise a feed summary into plain readable text.

    Feed entries arrive as raw markup — WordPress teaser paragraphs wrapped in
    ``<p>`` tags, arXiv announcements prefixed with their
    ``arXiv:IDvN Announce Type: ... Abstract:`` boilerplate — and this text
    flows verbatim into findings, clusters and the digest if left as-is.

    :param raw: The unprocessed feed summary.
    :returns: The plain-text summary, truncated to the candidate limit.
    """
    text = _FEED_MARKUP.sub(" ", unescape(raw))
    text = " ".join(text.split())
    text = _FEED_PREAMBLE.sub("", text)
    text = _ABSTRACT_LEAD.sub("", text)
    return text[:500]


def _entry_date(entry: Any) -> date | None:
    """Read a feed entry's publish (or update) date.

    :param entry: A feedparser entry.
    :returns: The date, or ``None`` when the entry carries none.
    """
    from email.utils import parsedate_to_datetime

    published_raw = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""
    try:
        return parsedate_to_datetime(published_raw).date()
    except TypeError, ValueError:
        struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        return date(struct.tm_year, struct.tm_mon, struct.tm_mday) if struct else None


def feed_coverage(xml: str) -> tuple[int, date | None]:
    """Report how much history a feed document carries.

    :param xml: The raw feed document.
    :returns: ``(entry count, oldest entry date)``; the date is ``None`` when no entry is dated.
    """
    import feedparser

    entries = feedparser.parse(xml).entries
    dates = [d for d in (_entry_date(entry) for entry in entries) if d]
    return len(entries), (min(dates) if dates else None)


def parse_feed_entries(xml: str, window_start: date, window_end: date) -> list[CandidateItem]:
    """Parse an RSS/Atom document into in-window candidate items.

    Deterministic: no LLM, no Firecrawl. Entries are filtered by publish date
    before any further work — only items inside the harvest window survive,
    so old feed history never reaches the gates. Every entry is considered:
    parsing costs nothing, and a busy feed's week can run past any fixed cap.

    :param xml: The raw feed document.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :returns: Candidates with real links and publish dates, in-window only.
    """
    import feedparser

    parsed = feedparser.parse(xml)
    items: list[CandidateItem] = []

    for entry in parsed.entries:
        link = getattr(entry, "link", "") or ""
        if not link:
            continue

        entry_date = _entry_date(entry)

        # Undated entries stay in (the gate handles unknown dates); dated
        # entries outside the window are dropped here, for free.
        if entry_date is not None and not (window_start <= entry_date <= window_end):
            continue

        items.append(
            CandidateItem(
                title=(getattr(entry, "title", "") or "").strip(),
                url=link,
                date=entry_date.isoformat() if entry_date else "",
                summary=_clean_feed_summary(getattr(entry, "summary", "") or ""),
            )
        )
    return items


async def harvest_feed_source(
    ctx: HarvestContext,
    services: Services,
    source: schemas.SourceEntry,
    window_start: date,
    window_end: date,
    prior: list[FindingsFile],
    themes: list[schemas.ThemeDef],
    snapshot: list[CandidateItem] | None = None,
) -> tuple[list[Finding], list[RejectedItem], SourceOutcome]:
    """One feed-channel source: parse its RSS/Atom directly, gate the entries.

    Feeds are deterministic XML — fetched with a plain GET and parsed with
    feedparser, so the listing step costs no Firecrawl call and no extraction
    judgement call. Entries carry real links and publish dates; each still
    goes through the full verification gate (cached item scrape + merged
    gate call). Entries captured earlier in the week by ``snapshot-feeds``
    are merged in, so a busy feed that no longer reaches back to Saturday
    still yields its whole week.

    A feed that cannot be fetched, or that is empty, falls back to scraping
    the source's page; both are flagged for the source-health check, as is
    a feed whose history no longer reaches the window start.

    :param ctx: The harvest context holding the LLM runners.
    :param services: The wired service clients.
    :param source: The due catalog source with a ``feed_url``.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :param prior: Recent findings files, for duplicate detection.
    :param themes: The watched themes.
    :param snapshot: This week's entries captured earlier by ``snapshot-feeds``.
    :returns: ``(findings, rejected, outcome)`` for the source.
    """
    feed_url = source.feed_url
    if not feed_url:
        # No feed declared: investigate the page the expensive way.
        return await harvest_web_source(ctx, services, source, window_start, window_end, prior, themes)

    xml = await services.crawl.fetch_feed(feed_url)
    entry_count, oldest = feed_coverage(xml) if xml is not None else (0, None)

    if xml is None or entry_count == 0:
        flag = "feed_fetch_failed" if xml is None else "feed_empty"
        findings, rejects, outcome = await harvest_web_source(
            ctx, services, source, window_start, window_end, prior, themes
        )
        outcome.flags.append(flag)
        outcome.detail = "; ".join(filter(None, [f"{flag}: {feed_url}", outcome.detail]))
        return findings, rejects, outcome

    candidates = parse_feed_entries(xml, window_start, window_end)
    seen = {normalize_url(c.url) for c in candidates}
    candidates += [c for c in (snapshot or []) if normalize_url(c.url) not in seen]

    flags = []
    if oldest is not None and oldest > window_start and not snapshot:
        flags.append("feed_truncated")

    verified, rejected = await gate_candidates(
        ctx, services, candidates, source, window_start, window_end, prior, themes, source.id, "direct"
    )

    return (
        verified,
        rejected,
        _log_outcome(
            SourceOutcome(
                source_id=source.id,
                status="collected" if verified or rejected else "empty",
                verified=len(verified),
                rejected=len(rejected),
                detail=f"feed reaches back only to {oldest.isoformat()}" if flags else "",
                flags=flags,
            )
        ),
    )


ARXIV_API = "https://export.arxiv.org/api/query"
ARXIV_PAGE_SIZE = 200


def arxiv_query_url(category: str, window_start: date, window_end: date, start: int = 0) -> str:
    """Build an arXiv API query for one category's submissions in a window.

    The RSS feeds only carry the latest daily announcement and are empty at
    weekends; the API answers for any date range.

    :param category: An arXiv category, e.g. ``"cs.AR"``.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :param start: Result offset, for pagination.
    :returns: The query URL.
    """
    from urllib.parse import urlencode

    query = f"cat:{category} AND submittedDate:[{window_start:%Y%m%d}0000 TO {window_end:%Y%m%d}2359]"
    params = {
        "search_query": query,
        "start": start,
        "max_results": ARXIV_PAGE_SIZE,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return f"{ARXIV_API}?{urlencode(params)}"


def parse_arxiv_entries(xml: str) -> tuple[list[CandidateItem], int]:
    """Parse one page of arXiv API results into candidates.

    :param xml: The Atom document the API returned.
    :returns: ``(candidates, total results for the query)``.
    """
    import feedparser

    parsed = feedparser.parse(xml)
    total = int(getattr(parsed.feed, "opensearch_totalresults", 0) or 0)
    items = []
    for entry in parsed.entries:
        link = getattr(entry, "link", "") or getattr(entry, "id", "")
        entry_date = _entry_date(entry)
        if not link:
            continue
        items.append(
            CandidateItem(
                title=" ".join((getattr(entry, "title", "") or "").split()),
                url=link,
                date=entry_date.isoformat() if entry_date else "",
                summary=_clean_feed_summary(getattr(entry, "summary", "") or ""),
            )
        )
    return items, total


async def harvest_arxiv_source(
    ctx: HarvestContext,
    services: Services,
    source: schemas.SourceEntry,
    window_start: date,
    window_end: date,
    prior: list[FindingsFile],
    themes: list[schemas.ThemeDef],
) -> tuple[list[Finding], list[RejectedItem], SourceOutcome]:
    """One arXiv category: the week's submissions from the API, gated.

    The API already gives each paper's title, abstract and date, so no page
    is scraped: the paper's abstract page stands in as the known page.

    :param ctx: The harvest context holding the LLM runners.
    :param services: The wired service clients.
    :param source: The due catalog source with an ``arxiv`` category.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :param prior: Recent findings files, for duplicate detection.
    :param themes: The watched themes.
    :returns: ``(findings, rejected, outcome)`` for the source.
    """
    import asyncio

    candidates: list[CandidateItem] = []
    start = 0
    while True:
        xml = await services.crawl.fetch_feed(arxiv_query_url(source.arxiv, window_start, window_end, start))
        if xml is None:
            return (
                [],
                [],
                SourceOutcome(
                    source_id=source.id, status="failed", detail="arXiv API unreachable", flags=["feed_fetch_failed"]
                ),
            )
        page, total = parse_arxiv_entries(xml)
        candidates.extend(page)
        start += ARXIV_PAGE_SIZE
        if not page or start >= total:
            break
        await asyncio.sleep(3)  # arXiv API etiquette: one request every three seconds

    known = {c.url: ScrapeResult(url=c.url, title=c.title, markdown=c.summary) for c in candidates}
    verified, rejected = await gate_candidates(
        ctx,
        services,
        candidates,
        source,
        window_start,
        window_end,
        prior,
        themes,
        source.id,
        "direct",
        known_pages=known,
    )

    return (
        verified,
        rejected,
        _log_outcome(
            SourceOutcome(
                source_id=source.id,
                status="collected" if verified or rejected else "empty",
                verified=len(verified),
                rejected=len(rejected),
            )
        ),
    )


async def harvest_web_source(
    ctx: HarvestContext,
    services: Services,
    source: schemas.SourceEntry,
    window_start: date,
    window_end: date,
    prior: list[FindingsFile],
    themes: list[schemas.ThemeDef],
) -> tuple[list[Finding], list[RejectedItem], SourceOutcome]:
    """One web-channel source (feed/scrape through the crawl service).

    :param ctx: The harvest context holding the LLM runners.
    :param services: The wired service clients.
    :param source: The due catalog source.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :param prior: Recent findings files, for duplicate detection.
    :param themes: The watched themes.
    :returns: ``(findings, rejected, outcome)`` for the source.
    """
    if source.skip:
        return (
            [],
            [],
            SourceOutcome(
                source_id=source.id,
                status="blocked",
                detail=f"skipped: {source.skip}",
            ),
        )

    page = await services.crawl.scrape(source.url)

    if page is None or not page.markdown:
        return [], [], SourceOutcome(source_id=source.id, status="failed", detail=f"scrape failed: {source.url}")

    candidates = (await ctx.extract_candidates(page.markdown)).items
    verified, rejected = await gate_candidates(
        ctx, services, candidates, source, window_start, window_end, prior, themes, source.id, "firecrawl"
    )

    return (
        verified,
        rejected,
        _log_outcome(
            SourceOutcome(
                source_id=source.id,
                status="collected" if verified or rejected else "empty",
                verified=len(verified),
                rejected=len(rejected),
            )
        ),
    )


async def harvest_newsletter_source(
    ctx: HarvestContext,
    services: Services,
    source: schemas.SourceEntry,
    messages: list,
    window_start: date,
    window_end: date,
    prior: list[FindingsFile],
    themes: list[schemas.ThemeDef],
) -> tuple[list[Finding], list[RejectedItem], SourceOutcome]:
    """Process one catalog source's attributed inbox messages as its newsletter channel.

    Messages are attributed to the source by sender before this is called;
    the newsletter itself is the primary source: the checked-in-body gate
    (``headline_in_body``) replaces the page-title comparison, and the final
    URL after the redirect chain goes into the finding.

    :param ctx: The harvest context holding the LLM runners.
    :param services: The wired service clients.
    :param source: The catalog source the messages were attributed to.
    :param messages: The attributed inbox messages for this source.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :param prior: Recent findings files, for duplicate detection.
    :param themes: The watched themes.
    :returns: ``(findings, rejected, outcome)`` for the source.
    """
    if services.mail is None:
        return [], [], SourceOutcome(source_id=source.id, status="failed", detail="mail service not configured")
    inbox = watch_settings.AGENTMAIL_INBOX_VISION_WATCH
    if not inbox:
        return [], [], SourceOutcome(source_id=source.id, status="failed", detail="harvest inbox not configured")

    candidates: list[CandidateItem] = []
    rejected: list[RejectedItem] = []
    for message in messages:
        body = await services.mail.get_message_text(inbox, message.message_id)
        for candidate in (await ctx.extract_candidates(body)).items:
            if not headline_in_body(candidate.title, body):
                rejected.append(_reject(candidate, source.id, "newsletter_mismatch"))
                continue
            resolved_url = candidate.url
            if page := await services.crawl.scrape(candidate.url):
                resolved_url = page.url or candidate.url
            candidates.append(_dated_by_message(candidate.model_copy(update={"url": resolved_url}), message))

    verified, gated_rejects = await gate_candidates(
        ctx, services, candidates, source, window_start, window_end, prior, themes, source.id, "newsletter"
    )
    rejected.extend(gated_rejects)

    return (
        verified,
        rejected,
        _log_outcome(
            SourceOutcome(
                source_id=source.id,
                status="collected" if verified or rejected else "empty",
                verified=len(verified),
                rejected=len(rejected),
            )
        ),
    )


async def harvest_inbox_unattributed(
    ctx: HarvestContext,
    services: Services,
    messages: list,
    window_start: date,
    window_end: date,
    prior: list[FindingsFile],
    themes: list[schemas.ThemeDef],
) -> tuple[list[Finding], list[RejectedItem], SourceOutcome]:
    """Newsletter content from senders the catalog doesn't cover yet.

    Real newsletter material with no catalog attribution; processed through
    the full verification gate with ``source_id: "inbox"`` — the curate task
    can propose adding recurring senders to the catalog.

    :param ctx: The harvest context holding the LLM runners.
    :param services: The wired service clients.
    :param messages: Unattributed inbox messages.
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :param prior: Recent findings files, for duplicate detection.
    :param themes: The watched themes.
    :returns: ``(findings, rejected, outcome)`` for the inbox fallback.
    """
    candidates: list[CandidateItem] = []
    for message in messages:
        body = message.text or (await _fetch_body(services, message))
        candidates.extend(_dated_by_message(c, message) for c in (await ctx.extract_candidates(body)).items)

    verified, rejected = await gate_candidates(
        ctx, services, candidates, None, window_start, window_end, prior, themes, "inbox", "newsletter"
    )
    return (
        verified,
        rejected,
        _log_outcome(
            SourceOutcome(
                source_id="inbox",
                status="collected" if verified or rejected else "empty",
                verified=len(verified),
                rejected=len(rejected),
            )
        ),
    )


_FORWARDED_FROM = re.compile(r"(?m)^\s*From:\s*(.+?)\s*$")


def _original_tipper(body: str) -> str | None:
    """Find the original sender named in a forwarded message body.

    A tip often reaches the agent inbox one hop late: someone mails the
    vision address, a colleague forwards it, and the envelope sender becomes
    the forwarder. Mail clients keep the original author in the quoted
    forward header (``From: Name <address>``), which credits the tip to the
    person who actually found it.

    :param body: The message body text.
    :returns: The quoted ``From:`` value, or ``None`` when the body carries
        no forward header.
    """
    match = _FORWARDED_FROM.search(body or "")
    if not match:
        return None

    return match.group(1).strip() or None


def _display_sender(sender: str) -> str:
    """Return a message sender as a human-readable name.

    ``"Eneko Illarramendi <eneko@x.be>"`` reads as ``"Eneko Illarramendi"``;
    a bare address stays a bare address.

    :param sender: The message's ``From`` value.
    :returns: The display name when one exists, the address otherwise.
    """
    if "<" in sender:
        name = sender.split("<", 1)[0].strip().strip('"').strip()
        if name:
            return name
    return sender.strip()


async def harvest_board_tips(
    ctx: HarvestContext,
    services: Services,
    messages: list,
    window_start: date,
    window_end: date,
    prior: list[FindingsFile],
    themes: list[schemas.ThemeDef],
) -> tuple[list[Finding], list[RejectedItem], SourceOutcome]:
    """Board tips: messages addressed to the board-tip mailbox.

    A tip is a lead, not a source in itself: the full verification gate
    applies against its primary URL. Only messages whose recipients include
    the board mailbox qualify — everything else in the inbox belongs to the
    newsletter attribution, not here.

    :param ctx: The harvest context holding the LLM runners.
    :param services: The wired service clients.
    :param messages: The board-tip-attributed inbox messages.
    :param prior: Recent findings files, for duplicate detection.
    :param themes: The watched themes.
    :returns: ``(findings, rejected, outcome)`` for the board-tip channel.
    """
    if services.mail is None:
        return [], [], SourceOutcome(source_id="board-tip", status="failed", detail="mail service not configured")
    inbox = watch_settings.AGENTMAIL_INBOX_VISION_WATCH
    if not inbox:
        return [], [], SourceOutcome(source_id="board-tip", status="failed", detail="harvest inbox not configured")

    verified: list[Finding] = []
    rejected: list[RejectedItem] = []
    for message in messages:
        body = await services.mail.get_message_text(inbox, message.message_id)
        # A forwarded tip credits its original author, not the forwarder.
        sender = _original_tipper(body) or message.from_
        links = extract_links(body)
        if not links:
            rejected.append(
                RejectedItem(
                    url="",
                    claimed_title=message.subject,
                    source_id="board-tip",
                    reason="board_tip_unresolved",
                    detail=f"board tip from {_display_sender(sender)}",
                )
            )
            continue
        page = await services.crawl.scrape(links[0])
        candidates = (await ctx.extract_candidates(body)).items
        candidate = (
            candidates[0] if candidates else CandidateItem(title=message.subject, url=page.url if page else links[0])
        )
        candidate = candidate.model_copy(update={"url": page.url if page else links[0]})
        findings, rejects = await gate_candidates(
            ctx,
            services,
            [candidate],
            None,
            window_start,
            window_end,
            prior,
            themes,
            "board-tip",
            "board-tip",
            tip=True,
        )
        for reject in rejects:
            reject.detail = f"board tip from {_display_sender(sender)}" + (
                f": {reject.detail}" if reject.detail else ""
            )

        if findings:
            findings[0].source_id = "board-tip"
            findings[0].summary = (findings[0].summary + f" [flagged by {_display_sender(sender)}]").strip()
            verified.extend(findings)
        else:
            rejected.extend(
                rejects
                or [
                    RejectedItem(
                        url=links[0],
                        claimed_title=message.subject,
                        source_id="board-tip",
                        reason="board_tip_unresolved",
                        detail=f"board tip from {_display_sender(sender)}",
                    )
                ]
            )
    return (
        verified,
        rejected,
        _log_outcome(
            SourceOutcome(
                source_id="board-tip",
                status="collected" if verified or rejected else "empty",
                verified=len(verified),
                rejected=len(rejected),
            )
        ),
    )


async def harvest_sweep(
    ctx: HarvestContext,
    services: Services,
    themes: list[schemas.ThemeDef],
    window_start: date,
    window_end: date,
    prior: list[FindingsFile],
) -> tuple[list[Finding], list[RejectedItem], SourceOutcome]:
    """Run the general sweep: one web search per theme, gated as usual.

    Catches developments from sources not yet in the catalog. Each search is
    bounded to the harvest window by a date range; hits are triaged before
    any scrape, and what survives goes through the full verification gate
    with ``source_id: "sweep"``.

    :param ctx: The harvest context holding the LLM runners.
    :param services: The wired service clients.
    :param themes: The watched themes, in config order (one search each).
    :param window_start: Window start (Saturday).
    :param window_end: Window end (Friday).
    :param prior: Recent findings files, for duplicate detection.
    :returns: ``(findings, rejected, outcome)`` for the sweep.
    """
    if services.crawl is None:
        return [], [], SourceOutcome(source_id="sweep", status="failed", detail="crawl service not configured")

    verified: list[Finding] = []
    rejected: list[RejectedItem] = []
    seen: set[str] = set()

    for theme in themes:
        query = theme.sweep_query or theme.question
        hits = [
            hit
            for hit in await services.crawl.search(query, limit=5, since=window_start, until=window_end)
            if normalize_url(hit.url) not in seen
        ]
        seen.update(normalize_url(hit.url) for hit in hits)
        if not hits:
            continue

        # Triage the hits before paying to scrape them: search noise dies here.
        kept = await ctx.triage([(hit.title, hit.description) for hit in hits], themes)
        candidates: list[CandidateItem] = []
        for i, hit in enumerate(hits):
            if i not in kept:
                continue
            page = await services.crawl.scrape(hit.url)
            if page is not None and page.markdown:
                extracted = (await ctx.extract_candidates(page.markdown)).items
            else:
                extracted = [CandidateItem(title=hit.title, url=hit.url, summary=hit.description)]
            candidates.extend(c.model_copy(update={"url": c.url or hit.url}) for c in extracted)

        findings, rejects = await gate_candidates(
            ctx, services, candidates, None, window_start, window_end, prior, themes, "sweep", "sweep", triaged=True
        )
        verified.extend(findings)
        rejected.extend(rejects)
    return (
        verified,
        rejected,
        _log_outcome(
            SourceOutcome(
                source_id="sweep",
                status="collected" if verified or rejected else "empty",
                verified=len(verified),
                rejected=len(rejected),
            )
        ),
    )


async def _fetch_body(services: Services, message) -> str:
    """Fetch one message's text body through the mail service.

    :param services: The wired service clients.
    :param message: The message to fetch.
    :returns: The message text; empty when the fetch fails.
    """
    inbox = watch_settings.AGENTMAIL_INBOX_VISION_WATCH
    if services.mail is None or not inbox:
        return ""
    return await services.mail.get_message_text(inbox, message.message_id)


def _log_outcome(outcome: SourceOutcome) -> SourceOutcome:
    """Log one source's outcome as it completes, so runs are observable live.

    :param outcome: The outcome to log.
    :returns: The outcome unchanged.
    """
    logger.info("source %s: %s (%dv/%dr)", outcome.source_id, outcome.status, outcome.verified, outcome.rejected)
    return outcome


def attribute_messages(
    messages: list,
    newsletter_sources: list[schemas.SourceEntry],
    board_mailbox: str,
) -> tuple[dict[str, list], list, list[schemas.SourceEntry]]:
    """Attribute inbox messages to newsletter sources, tips, or nothing.

    A message is a **board tip** when its recipients include the board
    mailbox (emails sent to the board's public address and redirected into
    the harvest inbox). Otherwise it is attributed to the catalog newsletter
    source whose declared senders match the message sender; messages that
    match no newsletter source go to the ``inbox`` fallback bucket — real
    newsletter content the catalog doesn't cover yet, i.e. curate candidates.

    :param messages: The inbox messages for the harvest window.
    :param newsletter_sources: The catalog's newsletter-flagged sources.
    :param board_mailbox: The board-tip mailbox address (e.g.
        ``tips@example.com``) matched against message recipients.
    :returns: ``(attributed, tips, unmatched_sources)`` — attributed maps
        source id to messages, ``tips`` is the board-tip message list, and
        ``unmatched_sources`` are the newsletter sources with no messages.
    """
    attributed: dict[str, list] = {source.id: [] for source in newsletter_sources}
    tips: list = []
    unattributed: list = []
    for message in messages:
        recipients = [r.lower() for r in message.to]
        if board_mailbox.lower() in recipients:
            tips.append(message)
            continue
        matched = next(
            (source for source in newsletter_sources if _sender_matches(message.from_, source.senders)),
            None,
        )
        if matched is not None:
            attributed[matched.id].append(message)
        else:
            unattributed.append(message)
    return attributed, tips, unattributed


def _sender_matches(message_from: str, senders: list[str]) -> bool:
    """Check a message sender against a catalog source's declared senders.

    Matched by substring in either direction, case-insensitive — a declared
    ``substack.com`` matches ``weekly@substack.com`` and vice versa. A message
    with no parsed sender matches nothing: the empty string is a substring of
    every declared value, so it would otherwise be attributed to whichever
    source happens to come first.

    :param message_from: The message sender address.
    :param senders: The source's declared sender addresses or domains.
    :returns: ``True`` when the sender matches any declared value.
    """
    lowered_from = (message_from or "").strip().lower()

    if not lowered_from:
        return False

    return any(declared.lower() in lowered_from or lowered_from in declared.lower() for declared in senders if declared)


def _window_start_dt(day: date) -> datetime:
    """Convert a window-start day to a UTC datetime for inbox queries.

    :param day: The window start.
    :returns: Midnight UTC of that day.
    """
    return datetime.combine(day, time.min, tzinfo=UTC)


def _window_end_dt(day: date) -> datetime:
    """Convert a window-end day to an exclusive UTC datetime for inbox queries.

    :param day: The window's closing Friday.
    :returns: Midnight UTC of the following day (exclusive upper bound).
    """
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC)
