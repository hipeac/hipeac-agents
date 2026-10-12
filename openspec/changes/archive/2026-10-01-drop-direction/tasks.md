# Tasks

## 1. Drop direction

- [x] 1.1 Remove `direction` from the verdict model and prompt (horizon stays), from `_judged`, `Finding`, `ClusterEntry` and the cluster node, and `Direction` from `schemas.py`; test that a verdict prompt no longer mentions direction and that a findings file and a cluster log written with `direction` still load; verify the full suite and `ruff check hipeac_agents` are clean
