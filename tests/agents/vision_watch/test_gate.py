"""The forward-looking gate: batched triage, undated and roundup rejects, verdict fields."""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.harvest import channels
from hipeac_agents.agents.vision_watch.nodes.harvest.context import TRIAGE_BATCH, HarvestContext
from hipeac_agents.agents.vision_watch.nodes.harvest.models import (
    CandidateItem,
    CandidateList,
    GateVerdict,
    TriageVerdict,
)
from hipeac_agents.services.factory import Services
from hipeac_agents.services.types import SearchHit
from tests.agents.vision_watch._fakes import FakeCrawl, FakeLLM


WINDOW = (date(2026, 9, 21), date(2026, 9, 27))  # 2026-W39, Monday–Sunday


@pytest.fixture(autouse=True)
def _alive(monkeypatch):
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.nodes.harvest.channels.http_url_is_dead", lambda url: False)


@pytest.fixture
def themes(data_dir):
    return workspace.read_themes(data_dir)


def _candidate(n: int, **overrides) -> CandidateItem:
    return CandidateItem(
        **{"title": f"Item {n}", "url": f"https://example.com/{n}", "date": "2026-09-22", "summary": "s", **overrides}
    )


def _verdict(**overrides) -> GateVerdict:
    return GateVerdict(**{"theme_ids": ["physical-ai"], "tier": 3, **overrides})


def _drop(*indices: int):
    return lambda prompt: TriageVerdict(items=[{"index": i, "keep": False} for i in indices])


async def _gate(llm, crawl, candidates, themes, **kwargs):
    return await channels.gate_candidates(
        HarvestContext(llm),
        Services(crawl=crawl, mail=None, vision=None),
        candidates,
        None,
        *WINDOW,
        [],
        themes,
        "sweep",
        "direct",
        **kwargs,
    )


class TestTriage:
    async def test_dropped_candidates_are_never_scraped(self, themes):
        """Regression (baseline B8/B9): a substring keyword pre-filter killed
        relevant news and let "Samsung" hit "SAMs"; one triage call per source
        now decides, and what it drops costs no scrape."""
        crawl = FakeCrawl(pages={f"https://example.com/{n}": (f"Item {n}", "t") for n in range(3)})
        llm = FakeLLM({TriageVerdict: _drop(1), GateVerdict: _verdict()})

        findings, rejected = await _gate(llm, crawl, [_candidate(n) for n in range(3)], themes)

        assert [f.url for f in findings] == ["https://example.com/0", "https://example.com/2"]
        assert [(r.url, r.reason) for r in rejected] == [("https://example.com/1", "off_theme")]
        assert "triage" in rejected[0].detail
        assert "https://example.com/1" not in crawl.scrape_calls
        assert sum(1 for schema, _ in llm.calls if schema is TriageVerdict) == 1

    async def test_free_checks_run_before_triage(self, themes):
        llm = FakeLLM({GateVerdict: _verdict()})

        _, rejected = await _gate(llm, FakeCrawl(), [_candidate(0, date="2026-01-01")], themes)

        assert rejected[0].reason == "out_of_window"
        assert not llm.calls

    async def test_triage_batches_and_keeps_what_it_does_not_mention(self, themes):
        prompts = []

        def triage(prompt):
            prompts.append(prompt)
            return TriageVerdict(items=[{"index": 0, "keep": False}])

        ctx = HarvestContext(FakeLLM({TriageVerdict: triage}))

        kept = await ctx.triage([(f"t{i}", "s") for i in range(TRIAGE_BATCH + 5)], themes)

        assert len(prompts) == 2
        assert kept == set(range(TRIAGE_BATCH + 5)) - {0, TRIAGE_BATCH}

    async def test_tips_skip_triage(self, themes):
        crawl = FakeCrawl(pages={"https://example.com/0": ("Item 0", "t")})
        llm = FakeLLM({TriageVerdict: _drop(0), GateVerdict: _verdict()})

        findings, _ = await _gate(llm, crawl, [_candidate(0)], themes, tip=True)

        assert len(findings) == 1


class TestVerdict:
    async def test_forward_fields_are_recorded(self, themes):
        crawl = FakeCrawl(pages={"https://example.com/0": ("Item 0", "t")})
        llm = FakeLLM({GateVerdict: _verdict(horizon="3-5y", forward_note="Could reset EU fab plans.", significance=4)})

        findings, _ = await _gate(llm, crawl, [_candidate(0)], themes)

        assert (findings[0].horizon, findings[0].forward_note, findings[0].significance) == (
            "3-5y",
            "Could reset EU fab plans.",
            4,
        )

    def test_verdict_no_longer_asks_for_a_direction(self):
        """Direction was never read after the verdict; it only cost output tokens."""
        from hipeac_agents.agents.vision_watch.nodes.harvest.prompts import GATE

        assert "direction" not in GATE.lower() and "strengthens" not in GATE
        assert "direction" not in GateVerdict.model_fields

    async def test_undated_item_is_rejected(self, themes):
        """Regression (baseline B10): an item with no date anywhere was recorded
        as this week's, which is how a 2023 paper became a W38 finding."""
        crawl = FakeCrawl(pages={"https://example.com/0": ("Item 0", "t")})

        findings, rejected = await _gate(FakeLLM({GateVerdict: _verdict()}), crawl, [_candidate(0, date="")], themes)

        assert findings == []
        assert rejected[0].reason == "undated"

    async def test_roundup_is_rejected(self, themes):
        crawl = FakeCrawl(pages={"https://example.com/0": ("Chip Industry Week In Review", "t")})

        _, rejected = await _gate(FakeLLM({GateVerdict: _verdict(is_roundup=True)}), crawl, [_candidate(0)], themes)

        assert rejected[0].reason == "roundup"

    async def test_unknown_question_id_is_off_theme(self, themes):
        crawl = FakeCrawl(pages={"https://example.com/0": ("Item 0", "t")})

        _, rejected = await _gate(
            FakeLLM({GateVerdict: _verdict(theme_ids=["no-such-question"])}), crawl, [_candidate(0)], themes
        )

        assert rejected[0].reason == "off_theme"


class TestSweep:
    async def test_hits_are_triaged_before_any_scrape(self, themes):
        hits = [SearchHit(url=f"https://example.com/hit{i}", title=f"Hit {i}", description="d") for i in range(2)]
        crawl = FakeCrawl(search_hits=hits, pages={"https://example.com/hit0": ("Hit 0", "page")})
        llm = FakeLLM(
            {
                TriageVerdict: _drop(1),
                GateVerdict: _verdict(theme_ids=[themes[0].theme]),
                CandidateList: lambda prompt: CandidateList(
                    items=[{"title": "Hit 0", "url": "https://example.com/hit0", "date": "2026-09-22"}]
                ),
            }
        )

        findings, _, _ = await channels.harvest_sweep(
            HarvestContext(llm), Services(crawl=crawl, mail=None, vision=None), themes[:1], *WINDOW, []
        )

        assert "https://example.com/hit1" not in crawl.scrape_calls
        assert [f.url for f in findings] == ["https://example.com/hit0"]
        assert crawl.search_calls == [themes[0].sweep_query or themes[0].description]


class TestSelectNotable:
    async def test_budget_is_enforced_and_invented_numbers_ignored(self, themes):
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import NotableSelection

        ctx = HarvestContext(FakeLLM({NotableSelection: NotableSelection(indices=[2, 99, 2, 0, 1])}))

        assert await ctx.select_notable([(f"t{i}", "") for i in range(5)], themes, budget=2) == [2, 0]

    async def test_long_lists_are_screened_in_rounds(self, themes):
        from hipeac_agents.agents.vision_watch.nodes.harvest.context import SELECT_BATCH
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import NotableSelection

        llm = FakeLLM({NotableSelection: NotableSelection(indices=[0, 1])})

        picked = await HarvestContext(llm).select_notable(
            [(f"t{i}", "") for i in range(SELECT_BATCH * 2 + 1)], themes, budget=2
        )

        assert picked == [0, 1]
        assert len(llm.calls) == 4, "three batches, then one final pick among their survivors"


class TestFewerCalls:
    async def test_busy_source_is_picked_down_before_the_verdict(self, themes):
        """Regression: busy sources had every candidate judged, then the
        4-per-source cap threw most verdicts away (191 in W39)."""
        from hipeac_agents.agents.vision_watch.nodes.harvest.channels import PREVERDICT_PICK
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import NotableSelection

        candidates = [_candidate(n) for n in range(20)]
        crawl = FakeCrawl(pages={c.url: (c.title, "t") for c in candidates})
        llm = FakeLLM({NotableSelection: NotableSelection(indices=[3, 1]), GateVerdict: _verdict()})

        findings, rejected = await _gate(llm, crawl, candidates, themes)

        assert [f.url for f in findings] == ["https://example.com/3", "https://example.com/1"]
        assert sum(r.reason == "source_cap" for r in rejected) == 18
        assert len(crawl.scrape_calls) == 2, "only picked candidates are scraped"
        assert PREVERDICT_PICK == 8

    async def test_verdicts_are_batched(self, themes):
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import GateBatch

        candidates = [_candidate(n) for n in range(6)]
        crawl = FakeCrawl(pages={c.url: (c.title, "t") for c in candidates})
        llm = FakeLLM({GateVerdict: _verdict()})

        findings, _ = await _gate(llm, crawl, candidates, themes)

        assert len(findings) == 6
        schemas = [schema for schema, _ in llm.calls]
        assert schemas.count(GateBatch) == 1
        assert GateVerdict not in schemas

    async def test_candidate_missing_from_a_batch_answer_is_judged_alone(self, themes):
        from hipeac_agents.agents.vision_watch.nodes.harvest.models import GateBatch, IndexedVerdict

        candidates = [_candidate(n) for n in range(3)]
        crawl = FakeCrawl(pages={c.url: (c.title, "t") for c in candidates})
        partial = GateBatch(
            verdicts=[
                IndexedVerdict(index=0, **_verdict().model_dump()),
                IndexedVerdict(index=9, **_verdict().model_dump()),
            ]
        )
        llm = FakeLLM({GateBatch: partial, GateVerdict: _verdict()})

        findings, _ = await _gate(llm, crawl, candidates, themes)

        assert len(findings) == 3
        assert sum(schema is GateVerdict for schema, _ in llm.calls) == 2, "indices 1 and 2 were missing"

    async def test_tips_are_judged_one_by_one_with_the_tip_rule(self, themes):
        candidates = [_candidate(n) for n in range(2)]
        crawl = FakeCrawl(pages={c.url: (c.title, "t") for c in candidates})
        llm = FakeLLM({GateVerdict: _verdict()})

        await _gate(llm, crawl, candidates, themes, tip=True)

        prompts = [prompt for schema, prompt in llm.calls if schema is GateVerdict]
        assert len(prompts) == 2
        assert all("board tip" in prompt for prompt in prompts)

    async def test_screening_calls_use_the_short_theme_outline(self, themes):
        llm = FakeLLM({TriageVerdict: _drop()})

        await HarvestContext(llm).triage([("t", "s")], themes)

        prompt = llm.calls[0][1]
        assert themes[0].outline() in prompt
        assert "Open questions" not in prompt


class TestNewsletterLinks:
    """Regression: newsletter click-trackers (Brevo, Substack redirects, web views) were recorded as
    findings' links and reached the digests; 41 of 844 findings over W26-W39."""

    TRACKER = "https://4ntll.r.sp1-brevo.net/mk/cl/f/sh/abc/def"

    async def test_tracker_is_followed_and_the_story_recorded(self, themes, monkeypatch):
        story = "https://example.com/story?utm_source=substack&utm_medium=email"
        monkeypatch.setattr(channels, "resolve_link", lambda url: story)
        crawl = FakeCrawl(pages={story: ("Item 0", "t")})

        findings, rejected = await _gate(
            FakeLLM({GateVerdict: _verdict()}), crawl, [_candidate(0, url=self.TRACKER)], themes, triaged=True
        )

        assert [f.url for f in findings] == ["https://example.com/story"]
        assert rejected == []
        assert crawl.scrape_calls == [story]

    async def test_tracker_that_resolves_nowhere_is_rejected(self, themes, monkeypatch):
        monkeypatch.setattr(channels, "resolve_link", lambda url: url)
        crawl = FakeCrawl(pages={self.TRACKER: ("Newsletter", "t")})

        findings, rejected = await _gate(
            FakeLLM({GateVerdict: _verdict()}), crawl, [_candidate(0, url=self.TRACKER)], themes, triaged=True
        )

        assert findings == []
        assert [(r.reason, r.detail) for r in rejected] == [("unresolved_link", f"ends on {self.TRACKER}")]

    async def test_page_ending_on_an_error_page_is_rejected(self, themes):
        crawl = FakeCrawl()

        async def scrape(url, fresh=False):
            from hipeac_agents.services.types import ScrapeResult

            return ScrapeResult(url="https://finance.yahoo.com/?err=404", title="Yahoo Finance", markdown="t")

        crawl.scrape = scrape
        findings, rejected = await _gate(
            FakeLLM({GateVerdict: _verdict()}), crawl, [_candidate(0)], themes, triaged=True
        )

        assert findings == []
        assert rejected[0].reason == "unresolved_link"


class TestResolveLink:
    """``resolve_link`` against a faked ``urlopen``: no network."""

    class _Response:
        def __init__(self, url: str, body: str = ""):
            self.url, self.body = url, body

        def geturl(self):
            return self.url

        def read(self, _size):
            return self.body.encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _serve(self, monkeypatch, routes: dict):
        import urllib.request

        def urlopen(request, timeout):
            answer = routes[request.full_url]
            if isinstance(answer, Exception):
                raise answer
            return answer

        monkeypatch.setattr(urllib.request, "urlopen", urlopen)

    def test_http_redirect(self, monkeypatch):
        from hipeac_agents.agents.vision_watch.nodes.harvest.gates import resolve_link

        self._serve(monkeypatch, {"https://substack.com/redirect/a": self._Response("https://example.com/story")})

        assert resolve_link("https://substack.com/redirect/a") == "https://example.com/story"

    def test_meta_refresh_on_the_trackers_page(self, monkeypatch):
        from hipeac_agents.agents.vision_watch.nodes.harvest.gates import resolve_link

        tracker = "https://4ntll.r.sp1-brevo.net/mk/cl/f/sh/a/b"
        page = '<noscript><meta http-equiv="refresh" content="0.0;https://example.com/story"></noscript>'
        self._serve(
            monkeypatch,
            {
                tracker: self._Response(tracker, page),
                "https://example.com/story": self._Response("https://example.com/story"),
            },
        )

        assert resolve_link(tracker) == "https://example.com/story"

    def test_tracker_leading_to_a_google_redirect(self, monkeypatch):
        from hipeac_agents.agents.vision_watch.nodes.harvest.gates import resolve_link

        google = "https://www.google.com/url?q=https%3A%2F%2Fexample.com%2Fstory&sa=D"
        self._serve(
            monkeypatch,
            {
                "https://substack.com/redirect/a": self._Response(google),
                "https://example.com/story": self._Response("https://example.com/story"),
            },
        )

        assert resolve_link("https://substack.com/redirect/a") == "https://example.com/story"

    def test_blocked_destination_still_names_its_url(self, monkeypatch):
        import urllib.error

        from hipeac_agents.agents.vision_watch.nodes.harvest.gates import resolve_link

        blocked = urllib.error.HTTPError("https://news.example.com/story", 403, "Forbidden", {}, None)
        self._serve(monkeypatch, {"https://t.e2ma.net/click/a": blocked})

        assert resolve_link("https://t.e2ma.net/click/a") == "https://news.example.com/story"

    def test_network_failure_keeps_the_link(self, monkeypatch):
        from hipeac_agents.agents.vision_watch.nodes.harvest.gates import resolve_link

        self._serve(monkeypatch, {"https://substack.com/redirect/a": TimeoutError()})

        assert resolve_link("https://substack.com/redirect/a") == "https://substack.com/redirect/a"


class TestNewsletterArrival:
    """Regression: a newsletter reporting last Friday's news had its item rejected as out of the week, and
    the week before never saw the email; 93 items over W26-W39 were recorded in no week."""

    async def test_newsletter_reports_last_weeks_news(self, themes):
        late = _candidate(0, date="2026-09-18", received="2026-09-22")
        crawl = FakeCrawl(pages={"https://example.com/0": ("Item 0", "t")})

        findings, rejected = await _gate(FakeLLM({GateVerdict: _verdict()}), crawl, [late], themes, triaged=True)

        assert [(f.url, f.date) for f in findings] == [("https://example.com/0", date(2026, 9, 18))]
        assert rejected == []

    async def test_newsletter_item_older_than_a_week(self, themes):
        old = _candidate(0, date="2026-09-14", received="2026-09-22")

        findings, rejected = await _gate(FakeLLM({GateVerdict: _verdict()}), FakeCrawl(), [old], themes)

        assert findings == []
        assert (rejected[0].reason, rejected[0].detail) == (
            "out_of_window",
            "near_window (7d outside) published 2026-09-14",
        )

    async def test_feed_item_before_the_week_gets_no_grace(self, themes):
        findings, rejected = await _gate(
            FakeLLM({GateVerdict: _verdict()}), FakeCrawl(), [_candidate(0, date="2026-09-18")], themes
        )

        assert findings == []
        assert rejected[0].reason == "out_of_window"

    async def test_newsletter_that_arrived_outside_the_week_gets_no_grace(self, themes):
        stale = _candidate(0, date="2026-09-18", received="2026-09-19")

        _, rejected = await _gate(FakeLLM({GateVerdict: _verdict()}), FakeCrawl(), [stale], themes)

        assert rejected[0].reason == "out_of_window"

    def test_message_records_arrival_and_dates_undated_items(self):
        from datetime import UTC, datetime
        from types import SimpleNamespace

        message = SimpleNamespace(timestamp=datetime(2026, 9, 22, 7, 30, tzinfo=UTC))

        dated = channels._dated_by_message(_candidate(0, date="2026-09-18"), message)
        undated = channels._dated_by_message(_candidate(1, date=""), message)

        assert (dated.date, dated.received) == ("2026-09-18", "2026-09-22")
        assert (undated.date, undated.received) == ("2026-09-22", "2026-09-22")

    def test_extraction_schema_never_asks_for_the_arrival(self):
        assert "received" not in str(CandidateList.model_json_schema())
