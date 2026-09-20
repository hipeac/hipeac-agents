"""Prompts for the harvest node's LLM judgement calls.

One prompt per structured-output model in ``models.py``. All five are
LLM-JUDGEMENT CALLS — review before the first live run.
"""

CANDIDATE_EXTRACTION = """\
You are collecting candidate developments for the HiPEAC Vision watch system.
From the page content below, extract individual developments: an announcement,
commitment, deployment, result, or report. Each item needs a title (as close to
the headline as possible), its URL (the primary URL for that item, not the
listing page), an ISO date if present, a one-sentence summary, and any notable
figure as the datapoint (e.g. "$900M acquisition"). Listings that aggregate
many developments yield many items; a single-article page yields one. Extract
at most 5 items — the most significant developments on the page. Return only
what the content actually contains — never invent items or URLs.
"""

GATE = """\
You are gating one candidate development for a HiPEAC Vision watch loop.
Answer three questions in one verdict:

1. THEMES: which of the watched themes does the candidate bear on, using each
theme's definition and keywords. Only include a theme when the development
genuinely relates to its definition — do not stretch keywords to fit.
Possibly empty. A candidate may bear on several themes.

2. TIER: the evidence tier per the development's state, not the source:
1 peer-reviewed results or reproducible benchmarks; 2 committed reality —
capital allocated, programmes adopted, hardware deployed; 3 stated intention
— announcements, proposals, specifications; 4 trade press, commentary,
aggregator analysis. Also extract the single most notable figure in the item,
if any, as the datapoint (e.g. "$900M", "1,200 jobs"); leave it empty otherwise.

3. TITLE: does the actual page title refer to the same announcement,
development, or subject as the claimed headline? Wording may differ; subject
may not. Set title_matches=false when the page is about something else, is a
listing or landing page that merely mentions the headline, or is an
error/paywall page — and say why in title_detail.

4. SUMMARY: one-sentence account of what happened (max 160 characters),
self-contained and specific — a busy researcher should get the story from
the sentence alone. Never copy the input summary verbatim when it runs
longer than two sentences; compress it. Leave empty only when the input
summary is already one clean sentence.

5. SIGNIFICANCE: how notable is this development for a European
computing-industry watch — 1 routine increment, 5 field-shifting result
or deployment. Judge from the item's content: novelty, scale of claims,
breadth of impact — never from how often its source publishes. Use the
full range: 2 for incremental workshop-quality work, 3 for solid results
of moderate interest, 4 for results that change what practitioners can
do or strong industry signals, 5 only for rare field-shifting results.
When torn between two scores, pick the lower.
"""

NEAR_MATCH = """\
You are applying the near-match rule: two outlets covering the same underlying
event — same entities, same numbers, same date, materially the same headline —
are ONE finding, not two. Group the findings below into groups of the same
underlying event. Findings that share no underlying event get their own
single-item group. Only group on the event, never on the theme.
"""
