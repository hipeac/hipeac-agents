## MODIFIED Requirements

### Requirement: Partial harvests

A harvest SHALL accept `--limit N` (check at most N due sources), `--only id1,id2` (check only these sources) and `--skip-sweep` (drop the per-theme web sweep), so an operator can run cheap partial harvests. With `--only`, the unattributed inbox, the board tips and the sweep SHALL run only when named (`inbox`, `board-tip`, `sweep`), and newsletters of sources left out SHALL not be read.

#### Scenario: Limited harvest

- **WHEN** the operator runs a harvest with `--limit 4 --skip-sweep`
- **THEN** only the first 4 due sources are checked and no web sweep runs

#### Scenario: Only some sources

- **WHEN** the operator runs a harvest with `--only arxiv-cs-ar`
- **THEN** no newsletter, tip or sweep is processed
