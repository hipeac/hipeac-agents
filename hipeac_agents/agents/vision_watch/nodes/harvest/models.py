"""Structured-output models for the harvest node's LLM judgement calls.

One model per judgement call, paired with the prompt of the same name in
``prompts.py``.
"""

from pydantic import BaseModel, Field

from hipeac_agents.agents.vision_watch.schemas import Direction, Horizon


class CandidateItem(BaseModel):
    """One candidate development extracted from a page or newsletter body."""

    title: str
    url: str
    date: str = Field(default="", description="ISO date of the development, empty if unknown")
    summary: str = ""
    datapoint: str = Field(default="", description="Notable figure, e.g. '$900M', empty if none")


class CandidateList(BaseModel):
    """Candidates extracted from one page or newsletter body."""

    items: list[CandidateItem] = []


class GateVerdict(BaseModel):
    """One candidate's verification verdict: themes, tier, and title match.

    Merged from what were three separate calls — one call per candidate keeps
    the weekly run affordable.
    """

    theme_ids: list[str] = Field(description="Ids of the watch questions the candidate moves; empty if none")
    tier: int = Field(description="Evidence tier per the development's state: 1-4")
    datapoint: str = Field(default="", description="Single most notable figure, e.g. '$900M'; empty if none")
    summary: str = Field(
        default="",
        description=(
            "One-sentence self-contained account of what happened, for the digest; "
            "empty only when the candidate summary is already a clean one-liner"
        ),
    )
    significance: int = Field(
        default=3,
        description=(
            "Forward importance for European computing, 1 (routine increment) "
            "to 5 (likely to reshape the field or Europe's position)"
        ),
    )
    direction: Direction | None = Field(
        default=None,
        description="How it moves its question: strengthens or weakens the current reading, or opens something new",
    )
    horizon: Horizon | None = Field(
        default=None, description="When its consequences land: now, within 1-2 years, or in 3-5 years"
    )
    forward_note: str = Field(
        default="", description="One line (max 160 chars): what this could change for European computing, and when"
    )
    is_roundup: bool = Field(
        default=False, description="The page is a digest or round-up of many items rather than one development"
    )

    title_matches: bool = Field(default=True, description="Page title refers to the same development as the headline")
    title_detail: str = Field(default="", description="Why the title does not match, when it does not")


class TriageItem(BaseModel):
    """One candidate's triage decision."""

    index: int = Field(description="The candidate's number in the list")
    keep: bool = Field(description="Whether it could move one of the watch questions")


class TriageVerdict(BaseModel):
    """Keep/drop decisions for one batch of candidates."""

    items: list[TriageItem] = []


class NearMatchGroups(BaseModel):
    """Groups of finding ids that are the same underlying event (near-match rule)."""

    groups: list[list[str]] = []
