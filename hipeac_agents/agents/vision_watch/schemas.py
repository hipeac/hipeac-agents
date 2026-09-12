"""Domain schemas for the vision-watch workspace files."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Region = Literal["eu", "global"]
Tier = Literal[1, 2, 3, 4]
RejectionReason = Literal[
    "out_of_window",
    "off_theme",
    "duplicate",
    "url_404",
    "title_mismatch",
    "newsletter_mismatch",
    "board_tip_unresolved",
    "unverified_sweep",
]
SourceClass = Literal[
    "programmes",
    "standards",
    "capital",
    "conferences",
    "ai-labs",
    "companies",
    "aggregators",
    "eu-uptake",
    "preprints",
    "open-source",
    "infrastructure-energy",
    "foresight",
    "community",
]
Independence = Literal["high", "med", "low"]
Stream = Literal["evidence", "signals"]
Chapter = Literal["future-ahead", "technology-roadmap"]

AccessMethod = Literal["direct", "firecrawl", "newsletter", "board-tip", "sweep"]


class Finding(BaseModel):
    """One verified development, as it appears in a weekly findings file."""

    id: str
    date: date
    title: str
    url: str
    source_id: str
    region: Region
    tier: Tier
    theme_ids: list[str] = []
    datapoint: str = ""
    summary: str
    access_method: AccessMethod | None = None
    corroboration: str | None = None


class FindingsFile(BaseModel):
    """Write-once weekly findings file (``findings-YYYY-Www.json``)."""

    week: str
    created: date
    generated_by: str = "harvest-sources"
    findings: list[Finding]


class RejectedItem(BaseModel):
    """One candidate the harvest considered and did not verify or record."""

    url: str
    claimed_title: str
    source_id: str
    reason: RejectionReason
    detail: str = ""
    summary: str = ""


class RejectedFile(BaseModel):
    """Write-once weekly audit file paired with the same week's findings."""

    week: str
    created: date
    generated_by: str = "harvest-sources"
    rejected: list[RejectedItem]


class ClusterEntry(BaseModel):
    """One finding appended to a cluster; never edited or removed."""

    week: str
    finding_id: str
    source_id: str
    source_class: SourceClass
    tier: Tier
    region: Region
    date: date
    title: str = ""
    note: str
    url: str


class Cluster(BaseModel):
    """A single ongoing development told over time, inside one theme's log."""

    id: str
    name: str
    opened: str
    entries: list[ClusterEntry]


class ClusterLog(BaseModel):
    """Append-only development-cluster log for one theme (``cluster-[theme].json``)."""

    theme: str
    created: date
    clusters: list[Cluster] = []


class ThemeDef(BaseModel):
    """A watched theme from the human-owned ``config/themes.yaml``."""

    theme: str
    chapter: Chapter
    definition: str
    keywords: list[str]
    sweep_query: str | None = None


class SourceEntry(BaseModel):
    """One source from the human-owned ``config/source-catalog.yaml``."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    url: str
    feed_url: str | None = None
    source_class: SourceClass = Field(alias="class")
    themes: list[str] = []
    region: Region
    tier: Tier
    independence: Independence
    stream: Stream
    senders: list[str] = []
    web: bool = True
    newsletter: bool = False
    bot_protected: bool = False
    last_verified: date | None = None
    notes: str | None = None


class SourceCatalog(BaseModel):
    """The parsed ``source-catalog.yaml`` document."""

    meta: dict[str, object] = {}
    sources: list[SourceEntry]
