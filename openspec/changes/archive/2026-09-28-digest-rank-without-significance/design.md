# Design

## Context

Story selection (`story_candidates` → `sort_lead_candidates`) keys on `-max(significance this week)` first; `novelty`, burst size, candidate-trend status and momentum only break ties. `story_material` renders each finding as `(source: X; significance N; horizon H)`. The thinking model writes the stories and the bottom line from at most 4 candidates per theme. Significance comes from the small model at gate time and is recorded once.

## Goals / Non-Goals

**Goals:**
- Story order and the prose call's framing no longer inherit the small model's significance bias.
- Stories that spread (new source classes, several classes this week) rise; single-outlet headlines sink.

**Non-Goals:**
- Changing significance at the gate, the per-source cap, or the monthly ranking.
- Making the digest longer (separate question: the 700-word target and "quiet is fine").

## Decisions

- **Key: novelty, this-week reach, this-week entries, candidate-trend, momentum.** Novelty already rewards what the Vision wants: a new story, or one reaching new classes or regions. This-week reach is new (distinct `source_class` among this week's entries): three outlets of different kinds beat one newsletter item. Alternative considered: let the thinking model pick from every touched cluster. Rejected for now: input grows with the week (77 findings in W39), and the cut to 4 per theme only filters crowded themes.
- **Hide significance, keep it for picking a story's findings.** Within one story the score only chooses which 4 findings to show, so its bias does not move stories between themes. Alternative: order the findings by source-class variety. Deferred; not needed for the observed skew.
- **One prompt line, no topic rule.** "Weigh by what it changes for the line's open questions, not by company size or money" rather than a rule against lab stories: labs sometimes are the story (e.g. access restrictions on a frontier model).

## Risks / Trade-offs

- [A consequential single-source event (e.g. the AI Act entering into force) ranks lower] → it still reaches the prose call unless its theme has more than 4 moving clusters; the prose call judges weight from the text.
- [Novelty favours brand-new one-off clusters] → this-week reach and entries break ties; the prose call may still leave a candidate out.
- [Evidence base is small: two weeks, one run each] → re-run W34, W38, W39 on a scratch copy after implementation and compare with the live digests before the next live run.
