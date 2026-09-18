"""CLI entrypoints for the vision-watch agent.

Usage::

    ./run python -m hipeac_agents weekly-harvest
    ./run python -m hipeac_agents weekly-digest [--send]
    ./run python -m hipeac_agents monthly-digest --month 2026-07 [--send]
    ./run python -m hipeac_agents simulate-harvest --on 2026-06-26 [--limit 4] [--skip-sweep]

Sending is opt-in: without ``--send`` a digest run composes and writes the
digest, and mails no one.
"""

import argparse
import logging
import os
import sys
from datetime import date

from hipeac_agents import settings
from hipeac_agents.agents.vision_watch import cadence, graph, workspace
from hipeac_agents.agents.vision_watch.state import VisionWatchState
from hipeac_agents.services.factory import load_services_async


HARVEST_NODES = ["harvest"]
DIGEST_NODES = ["cluster", "digest"]


def _llm_configured() -> bool:
    """Check whether an LLM provider is configured.

    :returns: ``True`` when a provider API key is present.
    """
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _build_llms() -> tuple[object, object]:
    """Build the two chat models: harvest judgement, and cluster/digest prose.

    Judgement calls are cheap classification tasks — a small model suffices
    and keeps the weekly run affordable; digest prose keeps the main model.
    Both run at temperature 0: same inputs must give same candidates, or the
    scrape cache stops paying off across runs.

    :returns: ``(judgement_llm, prose_llm)``.
    """
    from langchain.chat_models import init_chat_model

    judgement = init_chat_model(settings.LLM_JUDGEMENT_MODEL, model_provider=settings.LLM_PROVIDER, temperature=0)
    prose = init_chat_model(settings.LLM_MODEL, model_provider=settings.LLM_PROVIDER, temperature=0)
    return judgement, prose


def _initial_state(
    week: str,
    today: date | None = None,
    source_limit: int | None = None,
    source_only: list[str] | None = None,
    skip_sweep: bool = False,
    send: bool = False,
    month: str | None = None,
) -> VisionWatchState:
    """Build the initial graph state for a run.

    :param week: The week label (the ISO week of the closing Friday).
    :param today: The day the run is simulating; defaults to today.
    :param source_limit: Cap on the number of due sources checked.
    :param source_only: Only check these source ids.
    :param skip_sweep: Drop the general sweep (cheap partial runs).
    :param send: Send the composed digest by email (opt-in).
    :returns: The initial state.
    """
    window_start, window_end = cadence.current_window(today or date.today())
    return VisionWatchState(
        week=week,
        window_start=window_start,
        window_end=window_end,
        source_limit=source_limit,
        source_only=source_only or [],
        skip_sweep=skip_sweep,
        send=send,
        month=month,
    )


def _week_label(today: date | None = None) -> str:
    """Compute the current run's week label from its window.

    :param today: The day the run is simulating; defaults to today.
    :returns: e.g. ``"2026-W37"``.
    """
    return cadence.weekly_label(cadence.current_window(today or date.today())[1])


def _init_sentry() -> None:
    """Initialise the Sentry SDK when a DSN is configured."""
    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.SENTRY_DSN)


async def _run(
    nodes: list[str],
    today: date | None = None,
    data_dir: str | None = None,
    source_limit: int | None = None,
    source_only: list[str] | None = None,
    skip_sweep: bool = False,
    send: bool = False,
    month: str | None = None,
) -> int:
    """Run one graph invocation against the configured workspace.

    Everything is written into the real data dir: the week's evidence under
    ``evidence/<week>/`` (findings, rejected audit, and the scrape cache that
    keeps every Firecrawl markdown).

    :param nodes: The nodes to run, in order.
    :param today: The day the run is simulating (``--on``); defaults to today.
    :param data_dir: Optional workspace-root override (``--data-dir``).
    :param source_limit: Cap on the number of due sources checked.
    :param source_only: Only check these source ids.
    :param skip_sweep: Drop the general sweep (cheap partial runs).
    :param send: Send the composed digest by email (opt-in).
    :returns: The exit code.
    """
    if data_dir:
        from hipeac_agents.agents.vision_watch import settings as watch_settings

        watch_settings.DATA_DIR = data_dir

    _init_sentry()
    week = _week_label(today)

    services = await load_services_async()
    if services.crawl is not None:
        # The scrape cache is workspace-level and content-addressed (by URL
        # hash), so every markdown Firecrawl returns is reused across weeks.
        from hipeac_agents.services.crawl import CachedCrawl
        from hipeac_agents.services.factory import Services

        services = Services(
            crawl=CachedCrawl(services.crawl, workspace.cache_root()),
            mail=services.mail,
            vision=services.vision,
        )

        # Preflight: fail fast when the crawl provider is out of credits,
        # instead of churning every source into per-source failures.
        from hipeac_agents.services.crawl import ScrapeQuotaError

        try:
            probe = await services.crawl.scrape("https://example.com", fresh=True)
        except ScrapeQuotaError as exc:
            print(f"crawl provider out of credits: {exc}", file=sys.stderr)
            return 1
        if probe is None:
            print("warning: preflight scrape failed; crawl provider may be misconfigured", file=sys.stderr)

    missing = [name for name, client in (("crawl", services.crawl), ("mail", services.mail)) if client is None]

    if missing:
        print(f"skipped services (not configured): {', '.join(missing)}", file=sys.stderr)

    if not _llm_configured():
        print("no LLM provider configured (set OPENAI_API_KEY)", file=sys.stderr)
        return 1

    compiled = graph.build_graph(nodes, services, *_build_llms())
    result = await compiled.ainvoke(
        _initial_state(
            week,
            today,
            source_limit=source_limit,
            source_only=source_only or [],
            skip_sweep=skip_sweep,
            send=send,
            month=month,
        )
    )

    print(f"week {week}: findings={len(result['findings'])} rejected={len(result['rejected'])}")

    for outcome in result["source_outcomes"]:
        source_id = getattr(outcome, "source_id", None) if not isinstance(outcome, dict) else outcome["source_id"]
        status = getattr(outcome, "status", None) if not isinstance(outcome, dict) else outcome["status"]
        verified = getattr(outcome, "verified", None) if not isinstance(outcome, dict) else outcome["verified"]
        rejected = getattr(outcome, "rejected", None) if not isinstance(outcome, dict) else outcome["rejected"]
        print(f"  {source_id}: {status} ({verified}v/{rejected}r)")

    return 0


async def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    :param argv: Command-line arguments; defaults to ``sys.argv``.
    :returns: The exit code.
    """
    parser = argparse.ArgumentParser(prog="hipeac_agents")
    parser.add_argument("command", choices=["weekly-harvest", "weekly-digest", "monthly-digest", "simulate-harvest"])
    parser.add_argument("--on", help="simulate-harvest / weekly-digest: ISO date to execute on, e.g. 2026-06-26")
    parser.add_argument("--month", help="monthly-digest: calendar month to synthesise, e.g. 2026-07")
    parser.add_argument("--data-dir", help="workspace-root override (default: HIPEAC_AGENTS_DATA_DIR)")
    parser.add_argument("--limit", type=int, help="harvest: check at most N due sources (cheap partial runs)")
    parser.add_argument("--only", help="harvest: comma-separated source ids to check")
    parser.add_argument("--skip-sweep", action="store_true", help="harvest: drop the general sweep")
    parser.add_argument(
        "--send",
        action="store_true",
        help="digest: email the composed digest to the board list (default: compose and write only)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.command == "weekly-harvest":
        return await _run(
            HARVEST_NODES,
            source_limit=args.limit,
            source_only=args.only.split(",") if args.only else None,
            skip_sweep=args.skip_sweep,
        )

    if args.command == "weekly-digest":
        return await _run(
            DIGEST_NODES,
            today=date.fromisoformat(args.on) if args.on else None,
            data_dir=args.data_dir,
            send=args.send,
        )

    if args.command == "monthly-digest":
        if not args.month:
            parser.error("monthly-digest requires --month YYYY-MM (e.g. --month 2026-07)")
            return 2
        return await _run(
            ["monthly"],
            data_dir=args.data_dir,
            send=args.send,
            month=args.month,
        )

    if not args.on:
        parser.error("simulate-harvest requires --on YYYY-MM-DD (e.g. --on 2026-06-26 for a Friday-evening run)")
        return 2

    today = date.fromisoformat(args.on)
    if today.weekday() != 4:
        print(f"warning: {args.on} is a {today.strftime('%A')}; a simulated Friday run is the norm", file=sys.stderr)

    return await _run(
        HARVEST_NODES,
        today=today,
        data_dir=args.data_dir,
        source_limit=args.limit,
        source_only=args.only.split(",") if args.only else [],
        skip_sweep=args.skip_sweep,
    )


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
