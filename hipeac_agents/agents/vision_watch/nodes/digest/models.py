"""Structured-output models for the digest node's judgement calls.

Paired with ``DIGEST_STORIES`` and ``DIGEST_INTRO`` in ``prompts.py``.
"""

from pydantic import BaseModel, Field


BOTTOM_LINE_FIELD = (
    "One paragraph, 3-4 sentences: the 2-3 open questions that moved most this week and which way, "
    "citing 1-2 findings each inline as [short phrase](F<n>)"
)


class DigestItem(BaseModel):
    """One candidate told as a signal: the open question it moves, and which way."""

    story: str = Field(description="The candidate's story key, e.g. S3")
    question: str = Field(description="The id of the open question it bears on, e.g. agentic-ai.1, or NEW")
    lean: str = Field(
        description="2-5 words: the direction it pushes the answer, never a restatement of the question; "
        "for NEW, the topic"
    )
    title: str = Field(description="A short title, 3-6 words, no markdown")
    text: str = Field(
        description="Full story: 1-2 sentences; short item: one sentence. Cite findings inline as [short phrase](F<n>)"
    )
    brief: bool = Field(description="True for a one-line item, false for a full story")


class WeeklyDigest(BaseModel):
    """The week's digest: a headline, a bottom line, and one item per candidate that moves an answer."""

    headline: str = Field(description="The week's headline, at most 8 words, no markdown — the email subject")
    this_week: str = Field(description=BOTTOM_LINE_FIELD)
    items: list[DigestItem] = Field(default=[], description="Per theme, full stories first, then short items")


class WeeklyIntro(BaseModel):
    """A recorded week's bottom line, rewritten on its own."""

    this_week: str = Field(description=BOTTOM_LINE_FIELD)
