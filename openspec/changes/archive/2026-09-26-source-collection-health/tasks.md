# Tasks

## 1. Collection

- [x] 1.1 arXiv API channel with window-bounded queries and pagination
- [x] 1.2 Consider every feed entry; fall back to the page on empty or failed feeds; flag truncation
- [x] 1.3 `snapshot-feeds` command and snapshot merge at harvest
- [x] 1.4 Extraction prompt: newest dated items, up to 10

## 2. Source health

- [x] 2.1 Persist per-source reports (`sources.json`) at harvest
- [x] 2.2 Pure labelling rules and a readable report
- [x] 2.3 Health node after harvest; alert the dev list on change with `--send`
- [x] 2.4 Tests for channels, snapshots, labels, report and alert
