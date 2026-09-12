"""Structured-output models for the digest node's judgement calls.

Each is paired with a prompt of the same purpose in ``prompts.py``.
"""

from pydantic import BaseModel, Field


class DigestProse(BaseModel):
    """Prose for one digest item, in the documented anatomy."""

    lead: str = Field(description="Bold lead-in: what happened (no link, no date — the template adds the source line)")
    why_it_matters: str = Field(description="Consequence for the field or Europe")
    europe: str = Field(description="The European stake, tagged GAP | OPPORTUNITY | DEPENDENCY")
    maturity: str = Field(description="watch/trial/established, low/moderate/high with tally")


class InBrief(BaseModel):
    """The ~100-word In brief section of the digest."""

    text: str = Field(description="~100 words: the bottom line of the week")


class SignalGroup(BaseModel):
    """One prose blurb tying 2-3 off-theme rejects to a shared dynamic."""

    blurb: str = Field(description="One plain sentence naming the shared dynamic (no markdown, no links)")
    urls: list[str] = Field(description="2-3 of the given rejects' URLs that this blurb covers")


class SignalGroups(BaseModel):
    """The week's "Also worth watching" groups, mined from off-theme rejects."""

    groups: list[SignalGroup] = Field(
        default=[], description="At most 4 groups, strongest first; empty when nothing forms a coherent signal"
    )
