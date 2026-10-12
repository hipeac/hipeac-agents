# Design

## Context

A harvest ends with the health node, which writes `evidence/<week>/health.json` (write-once) even when the week yields no findings. `findings.json` is not a safe marker: a harvest with no findings still writes it, but a never-harvested week has neither. `workspace.read_health_file` already reads it. Weeks harvested before health reports existed lack the file.

## Goals / Non-Goals

**Goals:** make "digest before harvest" impossible to send; fail before any cost.
**Non-Goals:** a `--force` flag; gating `monthly-digest` (it has its own evidence gate); changing the send-once rule.

## Decisions

- **Marker is `health.json`**, last artifact of the harvest chain, so its presence means the harvest finished. Alternative `sources.json` is also optional in old weeks; `findings.json` can exist for partial runs.
- **Check lives in the CLI**, next to the other preflights, before `--redo` purges anything and before the graph is built. Pure synchronous code, no LLM, per the agent layout rules.
- **Ungated when a digest is recorded**, because the recorded digest was composed under the gate or is historical.
- **`--redo` ordering:** `weekly-digest --redo` keeps evidence, so it passes. Only a prior `weekly-harvest --redo` clears the marker, correctly forcing a re-harvest.

## Risks / Trade-offs

- Old weeks without `health.json` cannot be re-composed; mitigated by writing the marker by hand if ever needed. Accepted over adding a force flag (YAGNI).
- A harvest that crashes after evidence but before health leaves no marker, so the digest is refused; that is the intended outcome.
