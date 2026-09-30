"""replay-gate: the current gate over recorded weeks, and the cutover."""

from datetime import date

import pytest

import hipeac_agents.cli as cli
from hipeac_agents.agents.vision_watch import replay, workspace
from hipeac_agents.agents.vision_watch.nodes.harvest.context import HarvestContext
from hipeac_agents.agents.vision_watch.nodes.harvest.models import GateVerdict, NearMatchGroups, TriageVerdict
from hipeac_agents.agents.vision_watch.schemas import (
    Cluster,
    ClusterEntry,
    Finding,
    FindingsFile,
    RejectedFile,
    RejectedItem,
    SourceReport,
    SourcesFile,
)
from tests.agents.vision_watch._fakes import FakeLLM


WEEK = "2026-W39"


@pytest.fixture
def recorded(data_dir, monkeypatch):
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.DATA_DIR", data_dir)
    created = date(2026, 9, 26)
    workspace.write_findings_file(
        FindingsFile(
            week=WEEK,
            created=created,
            findings=[
                Finding(
                    id="f-2026-W39-01",
                    date=date(2026, 9, 22),
                    title="Robot surgery paper",
                    url="https://example.com/surgery",
                    source_id="robot-report",
                    region="global",
                    tier=1,
                    summary="A paper.",
                )
            ],
        )
    )
    workspace.write_rejected_file(
        RejectedFile(
            week=WEEK,
            created=created,
            rejected=[
                RejectedItem(
                    url="https://example.com/euv",
                    claimed_title="Intel and ASML collaborate on High-NA EUV",
                    source_id="darpa-news",
                    reason="off_theme",
                    summary="Lithography.",
                ),
                RejectedItem(
                    url="https://example.com/old", claimed_title="Old", source_id="eu-fund", reason="out_of_window"
                ),
            ],
        )
    )
    workspace.write_sources_file(
        SourcesFile(week=WEEK, created=created, sources=[SourceReport(source_id="robot-report", status="collected")])
    )
    return data_dir


def test_week_window():
    assert replay.week_window(WEEK) == (date(2026, 9, 19), date(2026, 9, 25))


def test_only_relevance_rejects_are_replayed(recorded):
    candidates, kept = replay.recorded_candidates(WEEK)

    assert [(c.source_id, c.was) for c in candidates] == [("robot-report", "finding"), ("darpa-news", "off_theme")]
    assert candidates[1].candidate.date == "2026-09-25", "rejects passed the window check: dated Friday"
    assert [r.reason for r in kept] == ["out_of_window"]


def test_plan_calls_counts_before_spending(recorded):
    candidates, _ = replay.recorded_candidates(WEEK)

    calls = replay.plan_calls({WEEK: candidates}, workspace.read_themes())

    assert {k: v for k, v in calls.items() if k != "est_input_tokens"} == {
        "weeks": 1,
        "candidates": 2,
        "triage_calls": 2,
        "pick_calls": 0,
        "verdict_calls": 2,
        "near_match_calls": 1,
    }
    assert 0 < calls["est_input_tokens"] < 20_000


def test_plan_calls_budget_busy_sources_to_a_pick(recorded):
    busy = [
        replay.RecordedCandidate("sifted", replay.CandidateItem(title=f"t{n}", url=f"https://x/{n}"), "off_theme")
        for n in range(45)
    ]

    calls = replay.plan_calls({WEEK: busy}, workspace.read_themes())

    assert (calls["triage_calls"], calls["pick_calls"], calls["verdict_calls"]) == (2, 1, 1)


async def test_replay_week_regates_and_reports(recorded, data_dir):
    def gate(prompt):
        if "High-NA EUV" in prompt:
            return GateVerdict(
                theme_ids=["agentic-ai"], tier=2, significance=4, horizon="3-5y", forward_note="EUV edge."
            )
        return GateVerdict(theme_ids=["physical-ai"], tier=1)

    llm = FakeLLM(
        {
            TriageVerdict: lambda prompt: TriageVerdict(items=[]),
            GateVerdict: gate,
            NearMatchGroups: NearMatchGroups(groups=[]),
        }
    )
    themes, catalog = workspace.read_themes(), workspace.read_source_catalog()

    findings_file, rejected_file, candidates = await replay.replay_week(
        HarvestContext(llm), WEEK, themes, catalog, prior=[]
    )

    assert {f.url for f in findings_file.findings} == {"https://example.com/surgery", "https://example.com/euv"}
    assert [r.reason for r in rejected_file.rejected] == ["out_of_window"]
    report = replay.render_report([(WEEK, findings_file, candidates)], themes, {"weeks": 1})
    assert "+1 gained, -0 dropped" in report
    assert "Intel and ASML collaborate on High-NA EUV" in report

    folder = replay.write_replay([(WEEK, findings_file, rejected_file)], report, "test")
    assert (folder / "evidence" / WEEK / "findings.json").exists()
    assert workspace.read_findings_file(WEEK).findings[0].url == "https://example.com/surgery", "live untouched"


async def test_replay_week_rejects_pages_recorded_in_an_earlier_week(recorded, data_dir):
    """Regression: replay ran the gate without the duplicate check, so one page
    backfilled into several weeks became a finding in each of them."""
    llm = FakeLLM(
        {
            TriageVerdict: lambda prompt: TriageVerdict(items=[]),
            GateVerdict: GateVerdict(theme_ids=["physical-ai"], tier=1),
            NearMatchGroups: NearMatchGroups(groups=[]),
        }
    )
    themes, catalog = workspace.read_themes(), workspace.read_source_catalog()
    earlier = FindingsFile(
        week="2026-W38",
        created=date(2026, 9, 19),
        findings=[workspace.read_findings_file(WEEK).findings[0].model_copy(update={"id": "f-2026-W38-01"})],
    )

    findings_file, rejected_file, _ = await replay.replay_week(
        HarvestContext(llm), WEEK, themes, catalog, prior=[earlier]
    )

    assert "https://example.com/surgery" not in {f.url for f in findings_file.findings}
    assert ("https://example.com/surgery", "duplicate") in {(r.url, r.reason) for r in rejected_file.rejected}


async def test_install_archives_v1_and_carries_source_reports(recorded, data_dir):
    workspace.append_cluster(
        Cluster(
            id="c",
            name="C",
            opened=WEEK,
            entries=[
                ClusterEntry(
                    week=WEEK,
                    finding_id="f-2026-W39-01",
                    source_id="robot-report",
                    source_class="press",
                    tier=1,
                    region="global",
                    date=date(2026, 9, 22),
                    note="n",
                    url="https://example.com/surgery",
                )
            ],
        ),
        theme="physical-ai",
        created=date(2026, 9, 26),
    )
    new = FindingsFile(week=WEEK, created=date(2026, 9, 26), generated_by="replay-gate", findings=[])
    folder = replay.write_replay(
        [(WEEK, new, RejectedFile(week=WEEK, created=date(2026, 9, 26), rejected=[]))], "#", "t"
    )

    weeks = replay.install_replay(folder)

    root = workspace.workspace_root()
    assert weeks == [WEEK]
    assert (root / "evidence-v1" / WEEK / "findings.json").exists()
    assert (root / "clusters-v1" / "physical-ai-clusters.json").exists()
    assert workspace.read_findings_file(WEEK).generated_by == "replay-gate"
    assert workspace.read_sources_file(WEEK) is not None
    assert workspace.week_cluster_entry_count(WEEK) == 0
    with pytest.raises(FileExistsError):
        replay.install_replay(folder)


async def test_cli_dry_run_spends_nothing(recorded, data_dir, monkeypatch, capsys):
    monkeypatch.setattr("hipeac_agents.cli.load_models", lambda: pytest.fail("a dry run must not build models"))

    exit_code = await cli.main(
        ["replay-gate", "--from", "2026-W30", "--to", WEEK, "--dry-run", "--data-dir", str(data_dir)]
    )

    assert exit_code == 0
    assert "'candidates': 2" in capsys.readouterr().out
