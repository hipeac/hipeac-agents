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


WINDOW = (date(2026, 9, 19), date(2026, 9, 25))


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
        llm = FakeLLM(
            {
                GateVerdict: _verdict(
                    direction="new", horizon="3-5y", forward_note="Could reset EU fab plans.", significance=4
                )
            }
        )

        findings, _ = await _gate(llm, crawl, [_candidate(0)], themes)

        assert (findings[0].direction, findings[0].horizon, findings[0].forward_note, findings[0].significance) == (
            "new",
            "3-5y",
            "Could reset EU fab plans.",
            4,
        )

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
        assert crawl.search_calls == [themes[0].sweep_query or themes[0].question]
