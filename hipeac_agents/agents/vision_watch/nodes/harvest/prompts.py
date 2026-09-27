"""Prompts for the harvest node's LLM judgement calls.

One prompt per structured-output model in ``models.py``; all are
LLM-JUDGEMENT CALLS.
"""

CANDIDATE_EXTRACTION = """\
You are collecting candidate developments for the HiPEAC Vision watch system.
From the page content below, extract individual developments: an announcement,
commitment, deployment, result, or report. Each item needs a title (as close to
the headline as possible), its URL (the primary URL for that item, not the
listing page), an ISO date if present, a one-sentence summary, and any notable
figure as the datapoint (e.g. "$900M acquisition"). Listings that aggregate
many developments yield many items; a single-article page yields one. Extract
at most 10 items — the NEWEST dated developments on the page, not the most
prominent: featured or pinned stories are often old. Always include the date
when the page shows one. Return only what the content actually contains —
never invent items or URLs.
"""

TRIAGE = """\
You are the first filter of a watch system feeding the HiPEAC Vision 2027, a
forward-looking roadmap for computing in Europe. The themes below are the
broad lines of the Vision; the watch collects signals inside them — what is
brewing, not only what happened: new advances, deployments, investments,
programmes and legislation in the pipeline, dependencies and risks that show
where computing is heading over the next years.

For each numbered candidate (title and summary), decide keep or drop:
- KEEP when it could plausibly be a signal for one of the themes: a technical
  advance, a deployment, money committed, a policy or regulation step, a
  standard, a security incident, a market or supply-chain shift, a credible
  forecast. Real-world names count (a programme, a company, a chip, a law):
  the news never uses the Vision's own vocabulary.
- DROP routine marketing, product promotions, event and webinar notices, job
  ads, hiring and personnel news, generic business news, and items with no
  bearing on computing.
When unsure, keep: a later step judges each kept item in full.
Return one decision per candidate, by its number.
"""

SELECT_NOTABLE = """\
You are screening a long list of research papers for the HiPEAC Vision 2027
watch, a forward-looking roadmap for computing in Europe. Most papers are
incremental; the watch wants only the few that are real signals for the
themes below: a result that changes what is possible, a new direction, a
strong benchmark or negative result, a survey mapping a shifting field, or
work tied to a major system, standard or policy.

Pick AT MOST {budget} papers from the numbered list, most notable first.
Fewer is fine; none is fine. Judge from the titles (and abstracts if given).
"""

GATE = """\
You are judging one candidate for the HiPEAC Vision 2027 watch, a
forward-looking roadmap for computing in Europe. The themes are the broad
lines of the Vision, each with open questions the next edition asks; the board
wants early signals of where each line is heading, not a log of what happened.
Answer in one verdict:

1. THEMES: which themes the candidate is a genuine signal for (theme_ids),
using each theme's description, open questions and what to look for. Do not
stretch. Possibly empty. A candidate may fit several.

2. DIRECTION and HORIZON: does it accelerate the trend the Vision describes
for that theme ("strengthens"), slow or contradict it ("weakens"), or open
something the Vision does not yet cover ("new"); and when do its consequences
land (now, 1-2y, 3-5y)?

3. FORWARD NOTE: one line (max 160 characters) on what this could change for
computing in Europe, and when. Concrete, no hype.

4. DATAPOINT: the single most notable figure in the item (e.g. "$900M",
"1,200 jobs"), if any.

5. TITLE: does the actual page title refer to the same development as the
claimed headline? Wording may differ; subject may not. Set
title_matches=false when the page is about something else, is a listing or
landing page that merely mentions the headline, or is an error/paywall page —
and say why in title_detail.

6. ROUNDUP: set is_roundup=true when the page is a weekly review, newsletter
issue, paper roundup or list of many unrelated items rather than one
development.

7. SUMMARY: one self-contained sentence (max 160 characters) of what
happened. Never copy a long input summary; compress it. Leave empty only when
the input summary is already one clean sentence.

8. SIGNIFICANCE: how much it tells about where computing is heading, 1-5:
1 routine increment; 2 incremental; 3 solid and worth tracking; 4 likely to
change what the field or Europe can or must do — a real advance, a binding
rule, a large commitment, a new dependency or risk; 5 rare, likely to reshape
the field. Judge the consequence, not the size of the headline or how often
the source publishes. When torn, pick the lower.
"""

NEAR_MATCH = """\
You are applying the near-match rule: two outlets covering the same underlying
event — same entities, same numbers, same date, materially the same headline —
are ONE finding, not two. Group the findings below into groups of the same
underlying event. Findings that share no underlying event get their own
single-item group. Only group on the event, never on the theme.
"""
