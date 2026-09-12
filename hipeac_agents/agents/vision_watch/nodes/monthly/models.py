"""Structured-output models for the monthly digest node."""

from pydantic import BaseModel, Field


class TrendProse(BaseModel):
    """One cluster's monthly synthesis, per the compose-digest monthly anatomy."""

    trend_name: str = Field(description="The trend named in plain language")
    evidence_summary: str = Field(
        description="The evidence so far: what the entries show, referencing the strongest sources"
    )
    why_it_matters: str = Field(description="Consequence for the field or for Europe")
    confidence: str = Field(description="How sure we are, backed by the tally")
    likelihood: str = Field(description="How likely the trend is to keep developing, separate from confidence")
    europe: str = Field(description="The European stake, tagged GAP | OPPORTUNITY | DEPENDENCY")
    recommendation: str = Field(description="One of: adopt into the Vision's thinking / keep watching / let go")


class MonthlyBottomLine(BaseModel):
    """The month's headline judgement, ~150 words."""

    text: str = Field(
        description="~150 words: the month's headline judgement and what the board might consider for the Vision"
    )
