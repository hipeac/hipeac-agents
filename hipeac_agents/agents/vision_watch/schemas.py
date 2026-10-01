"""Domain schemas for the vision-watch workspace files."""

from datetime import date
from functools import cached_property
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Region = Literal["eu", "global"]
RejectionReason = Literal[
    "out_of_window",
    "off_theme",
    "duplicate",
    "url_404",
    "unresolved_link",
    "title_mismatch",
    "newsletter_mismatch",
    "board_tip_unresolved",
    "unverified_sweep",
    "source_cap",
    "undated",
    "roundup",
]
Horizon = Literal["now", "1-2y", "3-5y"]

AccessMethod = Literal["direct", "firecrawl", "newsletter", "board-tip", "sweep"]
HealthLabel = Literal["ok", "skipped", "fetch_failed", "empty_feed", "truncated_feed", "stale_listing", "silent"]


class Finding(BaseModel):
    """One verified development, as it appears in a weekly findings file."""

    id: str
    date: date
    title: str
    url: str
    source_id: str
    region: Region
    theme_ids: list[str] = []
    datapoint: str = ""
    summary: str
    significance: int = 3
    access_method: AccessMethod | None = None
    corroboration: str | None = None
    horizon: Horizon | None = None
    forward_note: str = ""


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


class SourceReport(BaseModel):
    """How one source fared in a week's harvest, for the source-health check."""

    source_id: str
    status: str
    verified: int = 0
    rejected: int = 0
    reasons: dict[str, int] = {}
    flags: list[str] = []
    detail: str = ""


class SourcesFile(BaseModel):
    """Write-once per-source harvest report (``evidence/<week>/sources.json``)."""

    week: str
    created: date
    sources: list[SourceReport]


class HealthFile(BaseModel):
    """Write-once source-health labels for a week (``evidence/<week>/health.json``)."""

    week: str
    created: date
    labels: dict[str, HealthLabel]


class ClusterEntry(BaseModel):
    """One finding appended to a cluster; never edited or removed."""

    week: str
    finding_id: str
    source_id: str
    source_class: str
    region: Region
    date: date
    title: str = ""
    note: str
    url: str
    significance: int | None = None
    horizon: Horizon | None = None


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
    """A Vision line (theme) from the human-owned ``config/themes.yaml``.

    Themes are the broad lines of the HiPEAC Vision; the watch collects the
    signals inside them. ``title`` is the heading readers see (the id when
    empty), ``description`` says in plain words what the line covers,
    ``questions`` are the open questions the next Vision asks in it,
    ``look_for`` names real-world indicators (programmes, companies,
    products) since news never uses the Vision's own vocabulary, and
    ``keywords`` are optional hints.
    """

    theme: str
    description: str
    title: str = ""
    questions: list[str] = []
    look_for: list[str] = []
    keywords: list[str] = []
    sweep_query: str | None = None
    chapter: str = ""

    @property
    def heading(self) -> str:
        """The name readers see: the title, or the id when no title is set."""
        return self.title or self.theme

    @property
    def questions_by_id(self) -> dict[str, str]:
        """The open questions keyed by position: ``<theme>.1``, ``<theme>.2``, … in file order."""
        return {f"{self.theme}.{n}": question for n, question in enumerate(self.questions, 1)}

    def outline(self) -> str:
        """Render the theme in one short line, for screening calls that see many items.

        :returns: One line: id, description, and what to look for.
        """
        line = f"- {self.theme}: {' '.join(self.description.split())}"
        return line + (f" Look for: {', '.join(self.look_for)}" if self.look_for else "")

    def brief(self) -> str:
        """Render the theme for a judgement prompt.

        :returns: One line: id, description, open questions, and what to look for.
        """
        parts = [f"- {self.theme}: {self.description}"]
        if self.questions:
            parts.append(f"Open questions: {' '.join(self.questions)}")
        if self.look_for:
            parts.append(f"Look for: {', '.join(self.look_for)}")
        if self.keywords:
            parts.append(f"Hints: {', '.join(self.keywords)}")
        return " ".join(parts)


class LedgerEntry(BaseModel):
    """One printed digest item: which open question a story moved, and which way."""

    question_id: str
    question: str = ""
    lean: str
    theme: str
    cluster_id: str
    status: str
    early: bool
    finding_ids: list[str] = []
    title: str
    text: str


class LedgerFile(BaseModel):
    """A week's ledger (``digests/weekly/digest-<week>-ledger.json``), written with its digest."""

    week: str
    created: date
    entries: list[LedgerEntry] = []


class SourceClassDef(BaseModel):
    """One source class declared in the catalog: a kind of voice, not a channel.

    ``primary: false`` marks a class that reports or comments on others' news
    rather than announcing its own; ``weekly_cap`` bounds the class's findings
    per week, all its sources together.
    """

    about: str
    primary: bool = True
    weekly_cap: int | None = None


class SourceEntry(BaseModel):
    """One source from the human-owned ``config/source-catalog.yaml``.

    The channel follows from the fields: ``arxiv`` is an arXiv category read
    through the API, ``feed_url`` a feed, otherwise the page is scraped;
    ``senders`` adds the newsletter channel, and ``web: false`` makes a
    newsletter-only source. ``skip`` gives the reason a source is never
    checked (e.g. bot-protected).
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    url: str
    name: str = ""
    feed_url: str | None = None
    arxiv: str | None = None
    source_class: str = Field(alias="class")
    region: Region = "global"
    senders: list[str] = []
    web: bool = True
    skip: str | None = None

    @model_validator(mode="after")
    def _default_name(self) -> SourceEntry:
        self.name = self.name or self.id
        return self

    @property
    def newsletter(self) -> bool:
        """Whether the source also arrives by email (it declares senders)."""
        return bool(self.senders)


class SourceCatalog(BaseModel):
    """The parsed ``source-catalog.yaml`` document.

    On disk, sources are grouped under their class and every class is declared
    in ``classes``; in memory the sources are one flat list. Legacy
    ``independence`` keys, per class or per source, are ignored.
    """

    classes: dict[str, SourceClassDef] = {}
    sources: list[SourceEntry]

    @model_validator(mode="before")
    @classmethod
    def _flatten_groups(cls, data: Any) -> Any:
        if not isinstance(data, dict) or not isinstance(data.get("sources"), dict):
            return data
        flat = [
            {**entry, "class": source_class}
            for source_class, entries in data["sources"].items()
            for entry in entries or []
        ]
        return {**data, "sources": flat}

    @model_validator(mode="after")
    def _classes_declared(self) -> SourceCatalog:
        undeclared = sorted({s.source_class for s in self.sources} - set(self.classes))
        if undeclared:
            raise ValueError(f"source classes not declared in `classes`: {', '.join(undeclared)}")
        return self

    def class_of(self, source_id: str) -> str | None:
        """Look up a source's class.

        :param source_id: The source id.
        :returns: The class, or ``None`` when the source is not in the catalog.
        """
        return self._class_by_id.get(source_id)

    @cached_property
    def _class_by_id(self) -> dict[str, str]:
        return {source.id: source.source_class for source in self.sources}

    def is_primary(self, source_class: str) -> bool:
        """Whether a class announces its own news; undeclared classes never do.

        :param source_class: The class name.
        :returns: ``True`` for a declared primary class.
        """
        declared = self.classes.get(source_class)
        return declared is not None and declared.primary
