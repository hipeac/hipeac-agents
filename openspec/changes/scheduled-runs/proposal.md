# Proposal

## Why

Every run is started by hand on a laptop, against a synced copy of the Nextcloud workspace. The weekly loop only works if someone remembers to run it on Monday, and a run that crashes or never starts goes unnoticed. The `hipeac` web app already reads the digests and findings from `Agents/vision_watch` on the shared Nextcloud mount, expecting this app to write them there.

## What Changes

- The collection deploys as a Dokku app with no web process: a Docker image like `hipeac-mcp`'s (Python 3.14 slim, uv export, non-root uid 1000), and the workspace on the existing Dokku storage mount of the Nextcloud share (`HIPEAC_AGENTS_DATA_DIR` = `.../Agents/vision_watch`, cache included). Secrets go in `dokku config`, not `.env`.
- Dokku cron (`app.json`, UTC) runs the commands unattended, with sending on, at the times the README's crontab already gives:
  - daily 22:30: `snapshot-feeds` (Sunday's run covers the week's last day);
  - Monday 05:00: `weekly-harvest --send`, then `weekly-digest --send`, then `monthly-digest --send`, chained so a failed harvest stops the digests. The harvest sends too: on the server, the source-health mail is the only place a failing source shows.
- Sentry is set up as in `hipeac`: release from `GIT_REV`, an environment, and warnings sent as logs.
- A new `--check-in` flag, set only in the cron commands, makes a run check in with its Sentry cron monitor (project `hipeac-agents`); a missed or failed run alerts. A command that exits non-zero without raising (no LLM key, crawl out of credits, week still open) checks in as failed. Manual runs (backfills, local runs) send no check-in.
- The monitors' schedules are checked against `app.json` by a test, so the two cannot drift.

## Capabilities

### New Capabilities

### Modified Capabilities

- `platform`: Error reporting (release and environment on every event, warnings as logs); new requirement Scheduled run monitoring (`--check-in`, one cron monitor per command, exit code decides the status).

## Impact

- **Depends on** `monday-weeks`: the Monday schedule and `monthly-digest` without `--month` (latest complete month, skips one already composed) come from it.
- **Code:** `cli.py` (Sentry init, `--check-in` around each command), `settings.py` (release, environment), tests.
- **Deploy files:** `Dockerfile`, `app.json` (cron), `.dockerignore`; README section on the Dokku app, replacing the crontab example. `./run` stays the local wrapper.
- **Server (manual, once):** create the app, mount the storage, set the config, `ps:scale web=0` and `proxy:disable`; backfill June–August with `dokku run ... monthly-digest --month 2026-06` (then `-07`, `-08`).
- **Sentry:** the `hipeac-agents` project gets four cron monitors (`vision-watch-snapshot-feeds`, `-weekly-harvest`, `-weekly-digest`, `-monthly-digest`).
