# Design

## Context

The CLI (`hipeac_agents/cli.py`) is the only entry point. Each command returns an exit code from `main()`, and `__main__.py` raises it as `SystemExit`. Refusals return codes rather than raising: 1 for no LLM key or no crawl credits, 2 for an open week or a usage error. `_init_sentry()` is called inside each command path and passes only the DSN. `monday-weeks` already gives the Monday run order, `monthly-digest` without `--month`, and a README crontab (`0 5 * * 1` chain, `30 22 * * *` snapshot).

On the server side, `hipeac` and `hipeac-mcp` are Dokku apps built from a Dockerfile (Python 3.14 slim, `uv export` then `uv pip install --system`). The Nextcloud share is already a Dokku storage, and `hipeac` reads `Agents/vision_watch` from it read-only. `hipeac` runs as uid 1000 and sends `release=GIT_REV` to Sentry.

Dokku cron runs each `app.json` entry in a one-off container from the app image, on the host's timezone (UTC). The command is tokenised and exec'd without a shell, so `&&` needs an explicit `sh -c`. Each entry takes a `concurrency_policy`.

## Goals / Non-Goals

**Goals:**
- The weekly loop runs with nobody at a laptop, and a failed or missing run alerts in Sentry.
- Local runs stay as they are: `./run`, `.env`, no check-ins.

**Non-Goals:**
- Retries. A failed Monday is re-run by hand (`dokku cron:run`) after the cause is fixed. Most commands are write-once or skip what already exists, so a re-run is safe. The exception is a failed harvest, which needs `--redo`.
- A web process, health endpoint, queue, or Redis.
- Writing through WebDAV. Agent output is read by `hipeac` from the mount, not browsed in Nextcloud.

## Decisions

### Dokku cron, not a worker process

The container starts only when a job runs, and the schedule lives in `app.json` with the code. Alternatives:
- A `worker:` process running APScheduler or huey, like `hipeac`. This keeps a container up all week and adds a scheduler to test. Huey also needs Redis.
- Host crontab calling `dokku run`. This works, but the schedule lives outside the repo.

### Chained Monday entry via `sh -c`

One cron entry: `sh -c 'python -m hipeac_agents weekly-harvest --send --check-in && python -m hipeac_agents weekly-digest --send --check-in && python -m hipeac_agents monthly-digest --send --check-in'`, with `concurrency_policy: forbid`. The order is required: the digest reads the harvest's evidence, and the monthly reads the digest's ledger. Separate entries at fixed offsets would race whenever a harvest runs long. A new CLI command running all three was rejected: it would add a command to the runs spec just to get `&&`.

### `--check-in` flag, not automatic

With a DSN set, local runs from `.env` and `dokku run` backfills would otherwise check in to the production monitors. A manual `monthly-digest --month 2026-06` would mark the monitor OK or failed out of schedule. Keying on the environment was rejected, because `dokku run` shares the app's config. The flag sits in the `app.json` commands, so `dokku cron:run` checks in too, which is right for a re-run of a scheduled job.

### Check-in around the exit code

`sentry_sdk.crons.monitor` marks a run failed only when an exception escapes, so a `return 1` would check in OK. Instead, `main()` sends `capture_checkin(status=IN_PROGRESS)`, runs the command, and sends OK for code 0 or ERROR for anything else. On an exception it sends ERROR and re-raises, so the error is still reported. The flag is read before dispatch. Sentry is initialised once in `main()`, for every command, replacing the per-command `_init_sentry()` calls, so the check-in and the error reporting share one client. `--check-in` on a command without a monitor is a usage error. A usage error from argparse exits before any check-in, and the monitor then reports the run as missed.

### Monitor config in code, pinned to `app.json` by a test

Each check-in sends `monitor_config` (crontab schedule, UTC, margin, max runtime), so Sentry creates or updates the monitor on the first run and no UI setup is needed. The schedules live in one module-level mapping `command -> schedule`. A test reads `app.json`, finds each `hipeac_agents <command> ... --check-in` in the cron commands, and asserts that the entry's schedule equals the mapping's. Monitors created in the UI with check-ins only were rejected: that would leave a second copy of the schedule where no test can see it.

| Monitor | Schedule | Check-in margin | Max runtime |
|---|---|---|---|
| `vision-watch-snapshot-feeds` | `30 22 * * *` | 10 min | 15 min |
| `vision-watch-weekly-harvest` | `0 5 * * 1` | 10 min | 180 min |
| `vision-watch-weekly-digest` | `0 5 * * 1` | 190 min | 60 min |
| `vision-watch-monthly-digest` | `0 5 * * 1` | 250 min | 60 min |

The digest and monthly monitors share the harvest's cron time but start only after the commands before them finish. Their margin therefore covers the runtime of the earlier steps in the chain; otherwise every Monday would be reported missed.

### Sentry init like `hipeac`, minus the web parts

`sentry_sdk.init(dsn, release=GIT_REV, environment=SENTRY_ENVIRONMENT or "development", enable_logs=True, integrations=[LoggingIntegration(sentry_logs_level=logging.WARNING)])`. No tracing, no PII, no `before_send`: nothing here is known to be noisy yet. `GIT_REV` is set by Dokku on git deploys. `SENTRY_ENVIRONMENT=production` is set with `dokku config`. The default `development` keeps local crashes out of production alerts.

### Image like `hipeac-mcp`, user like `hipeac`

The image is `python:3.14-slim`, with uv pinned (as `hipeac` pins it). `uv export --no-dev --no-emit-project` then `uv pip install --system`, `COPY . /app`, and `useradd --uid 1000 app` with `USER app`. The storage mount is already owned for that uid. No build tools: every dependency ships wheels (verify on the first build). There is no `EXPOSE`, `CMD` or Procfile. `app.json` must stay in the image, since Dokku reads the cron from it. `.dockerignore` leaves out `.env*`, `data/`, `openspec/`, `tests/`, `.venv/`, `.git/` and the caches.

## Risks / Trade-offs

- [A failed harvest also makes the digest and monthly monitors report missed: three alerts for one cause] → The harvest's error check-in comes first and names the cause. The other two are expected, and the README says so.
- [Margins rest on a guessed harvest runtime] → They are tuned after the first live Mondays from the check-in durations (see Open Questions). A margin that is too short gives a false "missed", never a lost run.
- [`--send` from the first scheduled run mails the board unreviewed] → The first live week is decided in the Migration Plan. Nothing is sent twice, and a bad digest can only be followed by a correction mail by hand.

## Migration Plan

1. Land the code and deploy files after `monday-weeks` is archived: its migration (tasks 3.x) rewrites the live workspace, and the scheduled runs must start on the rebuilt one.
2. Server, once: `dokku apps:create hipeac-agents`; mount the existing Nextcloud storage at the data path; `dokku config:set` with the `.env` keys, plus `HIPEAC_AGENTS_DATA_DIR`, `SENTRY_DSN` (project `hipeac-agents`) and `SENTRY_ENVIRONMENT=production`; `git push dokku main`; `dokku ps:scale hipeac-agents web=0` and `dokku proxy:disable hipeac-agents`; `dokku cron:list hipeac-agents` to check both entries.
3. Smoke test: `dokku run hipeac-agents python -m hipeac_agents weekly-digest` with no `--send` for an already-composed week. It should report the digest exists and write nothing. Then `dokku cron:run` the snapshot entry, and confirm the Sentry monitor appears with an OK check-in.
4. Backfill the monthlies by hand: `dokku run hipeac-agents python -m hipeac_agents monthly-digest --month 2026-06 --send`, then `-07` and `-08`.
5. Rollback: `dokku cron:suspend` the entries, or `dokku ps:stop`. The workspace is unchanged, so local runs can resume against the synced copy.

## Open Questions

- How long does a live harvest take on the server? The margins above assume at most 3 h. Tune them from the first check-in durations.
