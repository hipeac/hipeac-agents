"""The source-health node: label sources, write the report, alert on change."""

import logging
from datetime import date
from typing import Any

from hipeac_agents.agents.vision_watch import settings as watch_settings
from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.schemas import HealthFile
from hipeac_agents.agents.vision_watch.state import VisionWatchState
from hipeac_agents.services.factory import Services
from hipeac_agents.services.mail import markdown_to_html

from .rules import QUIET, STREAK_WEEKS, activity_by_source, label_source, render_health_markdown, unhealthy


logger = logging.getLogger(__name__)


async def health_node(state: VisionWatchState, *, services: Services) -> dict[str, Any]:
    """Label every checked catalog source and report when the picture changes.

    Reads the week's per-source report written by the harvest, so it also
    works on its own. A week without a report (not harvested, or harvested
    before reports existed) or with a health report already is skipped. The
    alert goes to the dev list only when the set of unhealthy sources
    changed since the last report, and only with ``--send``.

    :param state: The graph state; carries the week and the ``send`` opt-in.
    :param services: The wired services (mail for the alert).
    :returns: State updates: notes.
    """
    week = state.week
    sources_file = workspace.read_sources_file(week)
    if sources_file is None or workspace.read_health_file(week) is not None:
        return {}

    catalog_ids = {source.id for source in workspace.read_source_catalog().sources}
    earlier = [w for w in workspace.list_weeks() if w < week][-(STREAK_WEEKS - 1) :][::-1]
    history = [activity_by_source(workspace.read_findings_file(w), workspace.read_rejected_file(w)) for w in earlier]

    reports = [r for r in sources_file.sources if r.source_id in catalog_ids]
    labels = {r.source_id: label_source(r, [weekly.get(r.source_id, QUIET) for weekly in history]) for r in reports}

    previous = next(
        (h for w in reversed(workspace.list_weeks()) if w < week and (h := workspace.read_health_file(w))), None
    )
    changed = unhealthy(labels) != (unhealthy(previous.labels) if previous else {})
    markdown = render_health_markdown(week, labels, reports, changed)
    workspace.write_health(HealthFile(week=week, created=date.today(), labels=labels), markdown)
    attention = len(unhealthy(labels))
    logger.info("source health %s: %d of %d sources need attention", week, attention, len(labels))

    inbox = watch_settings.AGENTMAIL_INBOX_VISION_WATCH
    recipient = watch_settings.HEALTH_ALERT_TO
    if changed and state.send and services.mail is not None and inbox and recipient:
        await services.mail.send(
            inbox,
            recipient,
            subject=f"vision-watch source health — {week}: {attention} sources need attention",
            text=markdown,
            html=markdown_to_html(markdown),
        )
        logger.info("source health alert sent to %s", recipient)

    return {"notes": [f"source health: {attention} of {len(labels)} sources need attention"]}
