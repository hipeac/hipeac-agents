"""Daily feed snapshots: keep a busy feed's whole week.

A feed carries only its newest entries; by Sunday a high-volume feed no
longer reaches back to Monday. ``snapshot-feeds`` runs daily, captures the
open week's entries, and the harvest merges them with the live feed. Pure
fetch-and-parse: no LLM, no crawl provider.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import date

from hipeac_agents.agents.vision_watch import cadence, workspace
from hipeac_agents.agents.vision_watch.nodes.harvest.channels import parse_feed_entries
from hipeac_agents.services.urls import normalize_url


logger = logging.getLogger(__name__)


async def snapshot_feeds(fetch: Callable[[str], Awaitable[str | None]], today: date) -> dict[str, int]:
    """Capture every feed source's entries for the week that is open today.

    :param fetch: Fetches a feed URL, returning the raw XML or ``None``.
    :param today: The day of the run.
    :returns: Source id to the number of entries held for the week after merging.
    """
    window_start, window_end = cadence.current_window(today)
    week = cadence.weekly_label(window_end)
    held: dict[str, int] = {}

    for source in workspace.read_source_catalog().sources:
        if not source.feed_url or source.arxiv or source.skip:
            continue

        xml = await fetch(source.feed_url)
        if xml is None:
            logger.info("snapshot %s: feed unreachable", source.id)
            continue

        known = workspace.read_feed_snapshot(week, source.id)
        seen = {normalize_url(item.url) for item in known}
        fresh = [
            item for item in parse_feed_entries(xml, window_start, window_end) if normalize_url(item.url) not in seen
        ]
        workspace.write_feed_snapshot(week, source.id, known + fresh)
        held[source.id] = len(known) + len(fresh)

    return held
