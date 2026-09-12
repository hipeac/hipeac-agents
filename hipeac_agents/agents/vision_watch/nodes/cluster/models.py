"""Structured-output models for the cluster node's LLM judgement call.

Paired with ``GROUPING_BAR`` in ``prompts.py``.
"""

from pydantic import BaseModel, Field


class NewCluster(BaseModel):
    """A new cluster object, opened the first week a development appears."""

    id: str = Field(description="kebab-case cluster id")
    name: str = Field(description="Short human-readable cluster name")
    theme: str = Field(description="Theme id the cluster belongs to")


class GroupingDecision(BaseModel):
    """One finding's cluster assignment, across any theme."""

    finding_id: str
    extends_cluster_id: str | None = Field(default=None, description="Existing cluster id this finding extends, if any")
    new_cluster: NewCluster | None = None


class GroupingPlan(BaseModel):
    """All assignments for the week's findings, across all themes."""

    assignments: list[GroupingDecision] = []
