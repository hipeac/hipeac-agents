# Proposal

## Why

Newsletters link their stories through click-trackers (Brevo, Substack redirects, e2ma, Mailchimp) or send readers to a "view in browser" page. The harvest recorded these as findings' links: 41 of 844 findings over W26–W39, cited in 12 weeklies and all three monthlies. Two reasons: the crawl provider's `_page_url` returned the URL requested (`source_url`) instead of where the scrape ended (`url`), and a tracker that redirects with a meta refresh (Brevo) or that the scrape could not open was kept as it came. Two more findings ended on an image (a YouTube thumbnail) and on an error page a dead article redirected to (`finance.yahoo.com/?err=404`).

## What Changes

- Before the liveness check and the scrape, a newsletter wrapper is followed to the story: HTTP redirects, a meta refresh on the tracker's page, a `google.com/url?q=` link.
- After the scrape, a candidate whose page is still a wrapper, an image or an error page is rejected `unresolved_link`.
- A finding records where the scrape ended, without per-send tracking parameters (`utm_*`, `_hsmi`, `_hsenc`, …).
- Citation link text is trimmed (`[ $3.36 billion …]`).

## Capabilities

### New Capabilities

### Modified Capabilities

- `vision-watch/candidate-verification`: Gate order step 5 follows newsletter wrappers and rejects links that reach no story (`unresolved_link`).

## Impact

- **Code:** `services/urls.py` (`is_link_wrapper`, `is_story_url`, `strip_tracking`, `unwrap_query_redirect`), `services/crawl.py` (`_page_url`), `nodes/harvest/gates.py` (`resolve_link`), `nodes/harvest/channels.py` (`_prepare_candidate`, `_judged`), `schemas.py` (`unresolved_link`), `nodes/digest/node.py` (`resolve_citations`).
- **Workspace:** repaired once on 2026-09-29: 42 finding links replaced across evidence, clusters, weeklies, signals logs, ledgers and monthlies; 2 findings with no reachable story moved to the audit as `unresolved_link` (the W34 story citing one of them removed); August's monthly recomposed. Backup in `_archive/vision-watch-before-link-repair-2026-09-29.tar.gz`. `rejected.json` keeps links as received.
