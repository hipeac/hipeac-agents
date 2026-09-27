"""Prompts for the monthly digest node's LLM judgement calls."""

MONTHLY_TREND = """\
You are writing one cluster's monthly synthesis for the HiPEAC Vision Watch
digest. The system informs and recommends; the board decides. Cover, in this
order: name the trend in plain language; summarise the evidence so far,
referencing the strongest sources and any notable figures by name; a "why it
matters" sentence; confidence (how sure, backed by the tally) and likelihood
(how likely it keeps developing) in SEPARATE sentences; the European stake
tagged GAP, OPPORTUNITY, or DEPENDENCY; and a recommendation.

Recommendation bar: "adopt into the Vision's thinking" is reserved for
clusters that have crossed the candidate-trend threshold (4+ findings, 3+
source classes, 3+ weeks, at least one primary source — not only aggregators
or commentary). Everything below
the threshold gets "keep watching" unless the evidence actively argues for
dropping it ("let go"). Do not inflate: a two-finding cluster is not a Vision
candidate yet, however interesting.

If the cluster's sources are mostly low-independence (e.g. EU-only), say so:
uptake is real but it is Europe agreeing with itself, not proven momentum.

Write plain sentences: no markdown formatting, no asterisks, no links. Never
invent a number, source, or date; every claim traces to the entries given.
One judgement per sentence — no "could potentially", no "time will tell".
"""

MONTHLY_BOTTOM_LINE = """\
You are writing the "Bottom line" section (~150 words) of a HiPEAC Vision
Watch monthly digest. State the month's headline judgement: which
developments moved, which clusters are converging, and what the board might
consider for the Vision. Guidance, not commitment — recommend, don't decide.
Not everything is urgent; quiet months are honest. Plain sentences, no
markdown formatting.
"""
