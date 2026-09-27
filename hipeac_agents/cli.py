"""CLI entrypoints for the vision-watch agent.

Usage::

    ./run python -m hipeac_agents weekly-harvest [--redo]
    ./run python -m hipeac_agents weekly-digest [--send] [--redo]
    ./run python -m hipeac_agents monthly-digest --month 2026-07 [--send]
    ./run python -m hipeac_agents simulate-harvest --on 2026-06-26 [--limit 4] [--skip-sweep]
    ./run python -m hipeac_agents snapshot-feeds        # daily: keep busy feeds' whole week
    ./run python -m hipeac_agents replay-gate --from 2026-W26 --to 2026-W39 [--dry-run]
    ./run python -m hipeac_agents replay-gate --apply <replay folder>

Sending is opt-in: without ``--send`` a digest run composes and writes the
digest, and mails no one.
"""

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from langchain_core.callbacks import get_usage_metadata_callback

from hipeac_agents import settings
from hipeac_agents.agents.vision_watch import cadence, graph, replay, snapshots, workspace
from hipeac_agents.agents.vision_watch.state import VisionWatchState
from hipeac_agents.llms import load_models, tiers, usage_lines
from hipeac_agents.services.factory import load_services_async


HARVEST_NODES = ["harvest", "health"]
DIGEST_NODES = ["cluster", "digest"]


def _llm_configured() -> bool:
    """Check whether an LLM provider is configured.

    :returns: ``True`` when a provider API key is present.
    """
    return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _initial_state(
    week: str,
    window: tuple[date, date],
    source_limit: int | None = None,
    source_only: list[str] | None = None,
    skip_sweep: bool = False,
    send: bool = False,
    month: str | None = None,
) -> VisionWatchState:
    """Build the initial graph state for a run.

    :param week: The week label (the ISO week of the closing Friday).
    :param window: The ``(saturday, friday)`` window the run targets.
    :param source_limit: Cap on the number of due sources checked.
    :param source_only: Only check these source ids.
    :param skip_sweep: Drop the general sweep (cheap partial runs).
    :param send: Send the composed digest by email (opt-in).
    :returns: The initial state.
    """
    window_start, window_end = window
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


def _target_window(on: date | None = None) -> tuple[date, date]:
    """Pick the weekly window a run targets.

    Without a date, the most recently closed Saturday–Friday window: a run on
    a Saturday targets the week that closed the day before, never the week
    that has just opened (harvesting an open week writes partial, write-once
    evidence). With a date, the window containing it.

    :param on: The ``--on`` date, if given.
    :returns: The ``(saturday, friday)`` window.
    :raises ValueError: If the window has not closed yet.
    """
    if on is None:
        return cadence.last_closed_window(date.today())

    window = cadence.current_window(on)
    if window[1] > date.today():
        raise ValueError(f"the week containing {on.isoformat()} closes on {window[1].isoformat()}, not yet")
    return window


def _use_data_dir(data_dir: str | None) -> None:
    """Point this run at another workspace root (``--data-dir``).

    :param data_dir: The override, or ``None`` to keep the configured root.
    """
    if data_dir:
        from hipeac_agents.agents.vision_watch import settings as watch_settings

        watch_settings.DATA_DIR = data_dir


async def _snapshot_feeds(data_dir: str | None) -> int:
    """Capture the open week's feed entries (``snapshot-feeds``).

    :param data_dir: Optional workspace-root override.
    :returns: The exit code.
    """
    from hipeac_agents.services.crawl import fetch_feed_direct

    _use_data_dir(data_dir)
    _init_sentry()
    held = await snapshots.snapshot_feeds(fetch_feed_direct, date.today())
    for source_id, count in sorted(held.items()):
        print(f"  {source_id}: {count} entries held this week")
    print(f"snapshot: {len(held)} feeds captured")
    return 0


async def _replay_gate(
    first: str | None, last: str | None, dry_run: bool, apply: str | None, data_dir: str | None
) -> int:
    """Replay the current gate over recorded weeks, or install a reviewed replay.

    :param first: The first week to replay (``--from``).
    :param last: The last week to replay (``--to``).
    :param dry_run: Only print the planned judgement calls.
    :param apply: A reviewed replay folder to swap into the workspace.
    :param data_dir: Optional workspace-root override.
    :returns: The exit code.
    """
    from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
    from hipeac_agents.services.factory import Services

    _use_data_dir(data_dir)
    _init_sentry()

    if not dry_run and not _llm_configured():
        print("no LLM provider configured (set OPENAI_API_KEY)", file=sys.stderr)
        return 1

    if apply:
        weeks = replay.install_replay(Path(apply))
        print(f"installed {len(weeks)} replayed weeks; archived evidence-v1/ and clusters-v1/")
        compiled = graph.build_graph(["cluster"], Services(crawl=None, mail=None, vision=None), load_models())
        with get_usage_metadata_callback() as usage:
            for week in weeks:
                await compiled.ainvoke(VisionWatchState(week=week))
                print(f"  {week}: re-clustered")
        _print_usage(usage.usage_metadata)
        return 0

    if not (first and last):
        print("replay-gate needs --from and --to week labels (e.g. --from 2026-W26 --to 2026-W39)", file=sys.stderr)
        return 2

    weeks = replay.weeks_between(first, last)
    candidates = {week: replay.recorded_candidates(week)[0] for week in weeks}
    calls = replay.plan_calls(candidates, workspace.read_themes())
    print(f"replay {first}..{last}: {calls}")
    print(f"  at most ~{calls['est_input_tokens']:,} input tokens on the small model ({tiers()['small']})")
    if dry_run:
        return 0

    _print_models()
    ctx = HarvestContext(load_models().small)
    themes, catalog = workspace.read_themes(), workspace.read_source_catalog()
    results = []
    with get_usage_metadata_callback() as usage:
        for week in weeks:
            findings_file, rejected_file, replayed = await replay.replay_week(ctx, week, themes, catalog)
            results.append((week, findings_file, rejected_file, replayed))
            print(f"  {week}: {len(findings_file.findings)} findings")
    _print_usage(usage.usage_metadata)

    report = replay.render_report([(w, f, c) for w, f, _r, c in results], themes, calls)
    folder = replay.write_replay([(w, f, r) for w, f, r, _c in results], report, f"{first}_{last}")
    print(f"replay written to {folder} — review report.md, then: replay-gate --apply {folder}")
    return 0


def _print_models() -> None:
    """Say which model each tier runs on, so a wrong setting shows up at once."""
    print("models: " + ", ".join(f"{name}={tier}" for name, tier in tiers().items()))


def _print_usage(usage: dict) -> None:
    """Print the run's token usage per model.

    :param usage: Model name to usage metadata, as collected during the run.
    """
    if usage:
        print("token usage:")
        for line in usage_lines(usage):
            print(line)


def _init_sentry() -> None:
    """Initialise the Sentry SDK when a DSN is configured."""
    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.SENTRY_DSN)


async def _run(
    nodes: list[str],
    window: tuple[date, date] | None = None,
    data_dir: str | None = None,
    source_limit: int | None = None,
    source_only: list[str] | None = None,
    skip_sweep: bool = False,
    send: bool = False,
    month: str | None = None,
    redo: bool = False,
) -> int:
    """Run one graph invocation against the configured workspace.

    Everything is written into the real data dir: the week's evidence under
    ``evidence/<week>/`` (findings, rejected audit, and the scrape cache that
    keeps every Firecrawl markdown).

    :param nodes: The nodes to run, in order.
    :param window: The targeted ``(saturday, friday)`` window; monthly runs have none.
    :param data_dir: Optional workspace-root override (``--data-dir``).
    :param source_limit: Cap on the number of due sources checked.
    :param source_only: Only check these source ids.
    :param skip_sweep: Drop the general sweep (cheap partial runs).
    :param send: Send the composed digest by email (opt-in).
    :param month: The calendar month for a monthly run.
    :param redo: Set the week's files aside first, so it is redone from scratch.
    :returns: The exit code.
    """
    _use_data_dir(data_dir)
    _init_sentry()
    window = window or cadence.last_closed_window(date.today())
    week = cadence.weekly_label(window[1])

    services = await load_services_async()
    if services.crawl is not None and "harvest" in nodes:
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

    if redo:
        backup = workspace.purge_week(week, keep_evidence="harvest" not in nodes)
        print(f"week {week} set aside for a redo; backup in {backup}")

    _print_models()
    compiled = graph.build_graph(nodes, services, load_models())
    with get_usage_metadata_callback() as usage:
        result = await compiled.ainvoke(
            _initial_state(
                week,
                window,
                source_limit=source_limit,
                source_only=source_only or [],
                skip_sweep=skip_sweep,
                send=send,
                month=month,
            )
        )
    _print_usage(usage.usage_metadata)

    if month:
        print(f"month {month}: digest {'sent' if result.get('digest_sent') else 'written'}")
        return 0

    findings, rejected = _week_counts(week, result)
    print(f"week {week}: findings={findings} rejected={rejected}")

    for outcome in result["source_outcomes"]:
        source_id = getattr(outcome, "source_id", None) if not isinstance(outcome, dict) else outcome["source_id"]
        status = getattr(outcome, "status", None) if not isinstance(outcome, dict) else outcome["status"]
        verified = getattr(outcome, "verified", None) if not isinstance(outcome, dict) else outcome["verified"]
        rejected = getattr(outcome, "rejected", None) if not isinstance(outcome, dict) else outcome["rejected"]
        print(f"  {source_id}: {status} ({verified}v/{rejected}r)")

    return 0


def _week_counts(week: str, result: dict) -> tuple[int, int]:
    """Count the week's findings and rejected items for the run summary.

    A digest run carries no evidence in its graph state, so the counts come
    from the week's recorded files rather than reading as an empty week.

    :param week: The week label.
    :param result: The final graph state.
    :returns: ``(findings, rejected)``.
    """
    if result["findings"] or result["rejected"]:
        return len(result["findings"]), len(result["rejected"])

    findings_file = workspace.read_findings_file(week)
    rejected_file = workspace.read_rejected_file(week)
    return (
        len(findings_file.findings) if findings_file else 0,
        len(rejected_file.rejected) if rejected_file else 0,
    )


async def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    :param argv: Command-line arguments; defaults to ``sys.argv``.
    :returns: The exit code.
    """
    parser = argparse.ArgumentParser(prog="hipeac_agents")
    parser.add_argument(
        "command",
        choices=[
            "weekly-harvest",
            "weekly-digest",
            "monthly-digest",
            "simulate-harvest",
            "snapshot-feeds",
            "replay-gate",
        ],
    )
    parser.add_argument("--on", help="harvest / weekly-digest: run for the week containing this ISO date")
    parser.add_argument("--month", help="monthly-digest: calendar month to synthesise, e.g. 2026-07")
    parser.add_argument("--from", dest="first", help="replay-gate: first week label, e.g. 2026-W26")
    parser.add_argument("--to", dest="last", help="replay-gate: last week label, e.g. 2026-W39")
    parser.add_argument("--dry-run", action="store_true", help="replay-gate: only print the planned judgement calls")
    parser.add_argument(
        "--apply", help="replay-gate: install a reviewed replay folder (archives evidence and clusters)"
    )
    parser.add_argument("--data-dir", help="workspace-root override (default: HIPEAC_AGENTS_DATA_DIR)")
    parser.add_argument("--limit", type=int, help="harvest: check at most N due sources (cheap partial runs)")
    parser.add_argument("--only", help="harvest: comma-separated source ids to check")
    parser.add_argument("--skip-sweep", action="store_true", help="harvest: drop the general sweep")
    parser.add_argument(
        "--redo",
        action="store_true",
        help="harvest / weekly-digest: back the week up and redo it (clears its cluster entries)",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="digest: email the digest to the board; harvest: email source-health changes to the dev list",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.command == "snapshot-feeds":
        return await _snapshot_feeds(args.data_dir)

    if args.command == "replay-gate":
        return await _replay_gate(args.first, args.last, args.dry_run, args.apply, args.data_dir)

    if args.command == "simulate-harvest" and not args.on:
        parser.error("simulate-harvest requires --on YYYY-MM-DD (e.g. --on 2026-06-26 for a Friday-evening run)")
        return 2

    on = date.fromisoformat(args.on) if args.on else None
    try:
        window = _target_window(on)
    except ValueError as exc:
        print(f"refusing to run: {exc}", file=sys.stderr)
        return 2

    if args.command in ("weekly-harvest", "simulate-harvest"):
        if on is not None and on.weekday() != 4:
            print(f"warning: {args.on} is a {on.strftime('%A')}; a simulated Friday run is the norm", file=sys.stderr)
        return await _run(
            HARVEST_NODES,
            window=window,
            data_dir=args.data_dir,
            source_limit=args.limit,
            source_only=args.only.split(",") if args.only else None,
            skip_sweep=args.skip_sweep,
            send=args.send,
            redo=args.redo,
        )

    if args.command == "weekly-digest":
        return await _run(
            DIGEST_NODES,
            window=window,
            data_dir=args.data_dir,
            send=args.send,
            redo=args.redo,
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

    return 2


if __name__ == "__main__":
    import asyncio

    raise SystemExit(asyncio.run(main()))
