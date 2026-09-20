"""Structured-output models for the harvest node's LLM judgement calls.

One model per judgement call, paired with the prompt of the same name in
``prompts.py``.
"""

from pydantic import BaseModel, Field


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

    theme_ids: list[str] = Field(description="Watched theme ids the candidate bears on; empty if none")
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
            "Editorial significance for the Vision watch, 1 (routine increment) "
            "to 5 (field-shifting result or deployment)"
        ),
    )

    title_matches: bool = Field(default=True, description="Page title refers to the same development as the headline")
    title_detail: str = Field(default="", description="Why the title does not match, when it does not")


class NearMatchGroups(BaseModel):
    """Groups of finding ids that are the same underlying event (near-match rule)."""

    groups: list[list[str]] = []
