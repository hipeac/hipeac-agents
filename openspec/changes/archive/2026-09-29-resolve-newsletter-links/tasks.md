# Tasks

## 1. Harvest

- [x] 1.1 URL helpers in `services/urls.py` (wrapper, story URL, tracking strip that keeps every other byte, query-carried redirect) and `resolve_link` in the harvest gates (HTTP redirects, meta refresh, blocked destination, no network in tests); test "Newsletter tracker" and "Tracker with no story behind it"
- [x] 1.2 `_page_url` takes where the scrape ended; `_prepare_candidate` follows wrappers first and rejects `unresolved_link`; `_judged` strips tracking; regression test against the provider's `url` / `source_url`
- [x] 1.3 Trim citation link text in `resolve_citations`; regression test

## 2. Workspace

- [x] 2.1 Repair the live workspace (backup first): links replaced, 2 findings moved to the audit, W34 story and counts, August monthly recomposed, stray spaces trimmed; no tracker, error page or `utm_` left in findings, clusters or digests
