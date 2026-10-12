# Proposal

## Why

The catalog had grown to 1,700 lines of per-source fields, several never read (`themes`, `last_verified`, `notes`), and 19 foresight "signals" sources that no code harvested. Matching sources to themes was pointless: every item is judged against every question.

## Changes

- Sources are grouped under their class; the class sets default tier and independence, overridable per source.
- The channel is inferred from the fields (`arxiv`, `feed_url`, `senders`, `web: false`); `skip: <reason>` replaces `bot_protected`.
- `stream`, `themes`, `newsletter`, `last_verified`, `notes` and `meta` are removed; every source is harvested, including the former signals stream.

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/source-collection`: catalog format, due list, skipped sources.
