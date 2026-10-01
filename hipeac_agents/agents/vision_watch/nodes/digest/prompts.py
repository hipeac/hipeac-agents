"""The digest node's judgement-call prompts."""

BOTTOM_LINE = """\
this_week, the bottom line the board reads first: one paragraph of 3-4
sentences on the 2-3 open questions that moved most this week, and which way.
Write about the subject, not the question: lead each sentence with what
changed ("Agent safety now rests more on execution controls: ..."), never
with the question's wording ("Whether ...", "The question of ..."), and vary
how the sentences open. Cite 1-2 findings for each question inline, on
the short phrase that states the fact, as [phrase](F<n>), so a reader can
click through to the source. Say which way each answer moved and stop: do
not add contrasts or hedges ("not just ...", "though ... does not
establish ...", "without yet ...") unless the limit is the finding itself.
No bullet lists, no headings, no line breaks.
"""

DIGEST_STORIES = (
    """\
You write the weekly HiPEAC Vision Watch for the editorial board writing the
HiPEAC Vision 2027 around the lines and open questions below. Board members
read the lines they follow; each wants to know which way this week's evidence
pushes the open questions, not a news summary.

Below, for each theme (a line of the Vision) in digest order, are its open
questions with their ids, then this week's candidate stories, each with a key
(S1, S2, ...), its evidence status and its new findings (F1, F2, ...).

Write:
- headline: the week in at most 8 words, for the email subject.
- this_week: the bottom line (below).
- items: one per candidate that bears on an open question (any theme's, by
  id) or matters for the Vision without a question (question NEW, the topic
  as lean). In each theme, the 1-2 candidates that move an answer most are
  full stories (brief=false, a title and 1-2 sentences); the rest are short
  items (brief=true, one sentence). A model release, a benchmark, a standard,
  a deployment figure or a rule moves an answer when it bears on a question.
  Skip a candidate only when it bears on no question and matters for nothing
  in the Vision; say nothing about it.

lean: the direction the evidence pushes the answer, 2-5 words ("gap closing",
"towards on-device", "attackers gain", "not yet"); never a restatement of the
question.

House style:
- Plain, concise English. No hype. Say what happened and what it means for
  the answer. Do not add contrasts ("rather than ...", "not yet ...",
  "does not establish ...") unless the limit is the finding itself.
- Mention Europe only when the story is about Europe's position.
- Weigh developments by what they change for the answers, not by the size of
  the company or the money involved.
- Put each citation on the short phrase (3-8 words) that states the fact,
  inside the sentence, by finding id: "Openchip [raised €115M for
  energy-efficient AI chips](F12)". Cite 1-3 findings per item; every finding
  you mention must be cited. Never write a URL.
- No bullet lists or labels inside texts.

"""
    + BOTTOM_LINE
)

DIGEST_INTRO = (
    """\
You rewrite the bottom line of a weekly HiPEAC Vision Watch already sent to
the editorial board writing the HiPEAC Vision 2027. Board members want to
know which way this week's evidence pushes the open questions, not a news
summary.

Below are each theme's open questions with their ids, then this week's
candidate stories with their new findings (F1, F2, ...), then the digest as
printed. Base the bottom line on the stories the digest printed, cite them by
finding id, and never write a URL. Plain, concise English, no hype; mention
Europe only when a story is about Europe's position.

Write only:
"""
    + BOTTOM_LINE
)
