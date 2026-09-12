"""Graph state for the vision-watch agent (pydantic, not TypedDict)."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from hipeac_agents.agents.vision_watch.schemas import Finding, RejectedItem


class SourceOutcome(BaseModel):
    """One due source's outcome for the run summary.

    A due source missing from the summary means the check didn't happen, not
    that it was quiet.
    """

    source_id: str
    status: str  # collected | blocked | empty | failed
    verified: int = 0
    rejected: int = 0
    detail: str = ""


class ClusterReport(BaseModel):
    """One theme's tally for this run, derived from its cluster log."""

    theme: str
    clusters_extended: int
    clusters_opened: int
    findings_unmatched: list[str] = []
    candidate_trends: list[str] = []
    notes: list[str] = []


class VisionWatchState(BaseModel):
    """State flowing through the harvest -> cluster -> digest graph."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    week: str
    window_start: date | None = None
    window_end: date | None = None

    # Monthly digest: the calendar month (``YYYY-MM``) the run synthesises.
    month: str | None = None

    # Run knobs (CLI): limit/only slice the due list; skip_sweep drops the
    # general sweep for cheap, partial runs.
    source_limit: int | None = None
    source_only: list[str] = []
    skip_sweep: bool = False

    findings: list[Finding] = []
    rejected: list[RejectedItem] = []
    source_outcomes: list[SourceOutcome] = []
    notes: list[str] = []

    cluster_reports: list[ClusterReport] = []

    digest_markdown: str = ""
    digest_sent: bool = False
    skip_send: bool = False

    errors: list[str] = []
