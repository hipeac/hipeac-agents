# Tasks

Start after `monday-weeks` is archived (design: Migration Plan, step 1).

## 1. Sentry init

- [x] 1.1 `settings.py`: `GIT_REV` and `SENTRY_ENVIRONMENT` (default `development`); `.env.example` lists `SENTRY_ENVIRONMENT`; one Sentry init (release, environment, logs at warning) replaces `_init_sentry()`'s DSN-only call; tests "Deployed run" and "Local run" (fake `sentry_sdk.init`, assert its arguments); `./run pytest tests/test_cli.py` passes

## 2. Cron check-ins

- [x] 2.1 `hipeac_agents/monitoring.py`: the `command -> monitor config` mapping from the design table (slug `vision-watch-<command>`, crontab, UTC, margin, max runtime) and a check-in wrapper that sends in-progress, then OK on exit code 0 or ERROR on any other code or an exception (re-raised); no-op without a DSN; tests in `tests/test_monitoring.py` with a faked `capture_checkin`: "Scheduled harvest succeeds", "Run refuses without raising", "Run crashes", "Flag without a DSN"
- [x] 2.2 CLI `--check-in` on `weekly-harvest`, `weekly-digest`, `monthly-digest` and `snapshot-feeds`, wrapping the command's dispatch in `main()`; tests "Quiet Monday for the monthly" (exit 0 with nothing composed checks in OK) and "Manual backfill" (no flag, no check-in); README flag table gains `--check-in`

## 3. Deploy files

- [ ] 3.1 `Dockerfile` (python:3.14-slim, pinned uv, `uv export --no-dev --no-emit-project` + `uv pip install --system`, uid 1000 `app` user, no `EXPOSE`/`CMD`) and `.dockerignore` (`.env*`, `data/`, `openspec/`, `tests/`, `.venv/`, `.git/`, caches; keeps `app.json`); verify `docker build .` succeeds without build tools and `docker run --rm <image> python -m hipeac_agents --help` prints usage
- [x] 3.2 `app.json` cron: `30 22 * * *` snapshot entry and `0 5 * * 1` `sh -c` chain (harvest, weekly digest, monthly digest, each `--send --check-in`), both `concurrency_policy: forbid`; test "Schedule drift" parses `app.json` and asserts every `--check-in` command's schedule equals its monitor's, and that each monitored command appears exactly once
- [x] 3.3 README: a "Deployment" section replacing the crontab example (Dokku app, storage mount, config keys incl. `SENTRY_ENVIRONMENT=production`, `ps:scale web=0`, `proxy:disable`, `cron:list` / `cron:run` / `cron:suspend`, manual monthly backfill, the three alerts a failed harvest raises); `ruff format` + `ruff check hipeac_agents` clean, full suite passes

## 4. Rollout

- [ ] 4.1 Server setup and smoke test per the design's Migration Plan steps 2–3 (operator runs the `dokku` commands); verify `dokku cron:list hipeac-agents` shows both entries and the snapshot monitor shows an OK check-in in Sentry
- [ ] 4.2 Backfill the June–August monthlies with `dokku run ... monthly-digest --month 2026-0X --send`; verify the three `.sent.json` markers exist and `hipeac` lists the digests
- [ ] 4.3 After the first live Monday, compare check-in durations with the margins; adjust the mapping (and nothing else) if a monitor reported missed
