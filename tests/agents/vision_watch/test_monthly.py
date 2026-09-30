"""Monthly digest node tests (LLM and mail faked)."""

from datetime import date

import pytest

from hipeac_agents.agents.vision_watch import workspace
from hipeac_agents.agents.vision_watch.nodes.monthly import node as monthly_node_mod
from hipeac_agents.agents.vision_watch.nodes.monthly.models import (
    MonthlyDigest,
    NewTopic,
    QuestionAnswer,
    monthly_model,
)
from hipeac_agents.agents.vision_watch.nodes.monthly.node import (
    NOTHING_QUALIFIES,
    compose_monthly_markdown,
    evidence_gate,
    monthly_material,
)
from hipeac_agents.agents.vision_watch.schemas import LedgerEntry, LedgerFile, ThemeDef
from hipeac_agents.agents.vision_watch.state import VisionWatchState
from hipeac_agents.services.factory import Services
from tests.agents.vision_watch._fakes import FakeLLM, FakeMail


THEMES = [
    ThemeDef(theme="agentic-ai", title="Agentic AI", description="Agents.", questions=["Who holds the keys?"]),
    ThemeDef(theme="physical-ai", title="Physical AI", description="Robots.", questions=["Paid work?", "On site?"]),
]


def _entry(question_id: str, *, question: str = "", early: bool = False, status: str = "", **kwargs) -> LedgerEntry:
    questions = {qid: text for theme in THEMES for qid, text in theme.questions_by_id.items()}
    return LedgerEntry(
        question_id=question_id,
        question=question or questions.get(question_id, ""),
        lean=kwargs.pop("lean", "moving"),
        theme=kwargs.pop("theme", question_id.rsplit(".", 1)[0] if question_id != "NEW" else "physical-ai"),
        cluster_id=kwargs.pop("cluster_id", f"c-{question_id}"),
        status=status or ("emerging" if early else "strengthening"),
        early=early,
        title=kwargs.pop("title", "Title"),
        text=kwargs.pop("text", "Something [moved](https://x/1)."),
        **kwargs,
    )


def _ledger(week: str, *entries: LedgerEntry) -> LedgerFile:
    return LedgerFile(week=week, created=date(2026, 9, 29), entries=list(entries))


class TestMonthWeeks:
    def test_july_2026(self):
        assert monthly_node_mod.month_weeks("2026-07") == {f"2026-W{week}" for week in range(27, 32)}

    def test_next_months_first_week_is_not_included(self):
        """Regression: September 2026 also took W40, which runs into October."""
        assert monthly_node_mod.month_weeks("2026-09") == {"2026-W36", "2026-W37", "2026-W38", "2026-W39"}

    def test_week_across_two_months(self):
        """Monday 28 September to Sunday 4 October: four of its days are in October."""
        assert "2026-W40" in monthly_node_mod.month_weeks("2026-10")
        assert "2026-W40" not in monthly_node_mod.month_weeks("2026-09")

    def test_month_starting_on_a_friday(self):
        """1 May 2026 is a Friday: that week's Thursday is in April."""
        assert min(monthly_node_mod.month_weeks("2026-05")) == "2026-W19"
        assert "2026-W18" in monthly_node_mod.month_weeks("2026-04")

    def test_every_week_of_a_year_in_exactly_one_month(self):
        weeks = [week for month in range(1, 13) for week in monthly_node_mod.month_weeks(f"2026-{month:02d}")]

        assert len(weeks) == len(set(weeks)) == 53


def _month(*signals: tuple[str, LedgerEntry]) -> list[LedgerFile]:
    """Group ``(week, entry)`` pairs into the month's ledgers."""
    weeks: dict[str, list[LedgerEntry]] = {}
    for week, entry in signals:
        weeks.setdefault(week, []).append(entry)
    return [_ledger(week, *entries) for week, entries in weeks.items()]


def _recurring(question_id: str, weeks: tuple[str, ...] = ("2026-W36", "2026-W36", "2026-W37"), **kwargs):
    return [(week, _entry(question_id, **kwargs)) for week in weeks]


class TestLastCompleteMonth:
    @pytest.mark.parametrize(
        ("today", "expected"),
        [
            (date(2026, 10, 5), "2026-09"),  # Monday after W40: September ended with W39
            (date(2026, 9, 28), "2026-09"),  # Monday after W39, the last week of September
            (date(2026, 8, 3), "2026-07"),  # Monday after W31, 27 July - 2 August
            (date(2026, 8, 1), "2026-06"),  # Saturday: W31 still open, so July is not complete
            (date(2026, 7, 27), "2026-06"),  # Monday after W30: July still has W31 to come
            (date(2027, 1, 4), "2026-12"),  # Monday after W53, 28 December - 3 January
        ],
    )
    def test_monday_run_without_a_month(self, today, expected):
        assert monthly_node_mod.last_complete_month(today) == expected

    def test_month_not_complete(self):
        """W44 (26 October - 1 November) is October's last week."""
        assert not monthly_node_mod.month_is_complete("2026-10", date(2026, 10, 5))
        assert not monthly_node_mod.month_is_complete("2026-10", date(2026, 11, 1))
        assert monthly_node_mod.month_is_complete("2026-10", date(2026, 11, 2))


class TestEvidenceGate:
    def test_three_signals_in_two_weeks_qualify(self):
        gate = evidence_gate(_month(*_recurring("physical-ai.1", early=True)), THEMES)

        assert list(gate.questions) == ["physical-ai.1"]
        assert gate.thin == {}

    def test_one_early_signal(self):
        gate = evidence_gate([_ledger("2026-W37", _entry("physical-ai.1", early=True, title="Robot pilot"))], THEMES)

        assert gate.questions == {}
        assert [signal.entry.title for signal in gate.thin["physical-ai.1"]] == ["Robot pilot"]

    def test_two_signals_past_early_are_thin(self):
        gate = evidence_gate(_month(*_recurring("physical-ai.1", ("2026-W36", "2026-W37"))), THEMES)

        assert gate.questions == {}
        assert list(gate.thin) == ["physical-ai.1"]

    def test_three_signals_in_one_week_are_thin(self):
        gate = evidence_gate(_month(*_recurring("physical-ai.1", ("2026-W36",) * 3)), THEMES)

        assert list(gate.thin) == ["physical-ai.1"]

    def test_question_reworded(self):
        gate = evidence_gate(
            _month(*_recurring("agentic-ai.1", question="Who holds the old keys?")),
            THEMES,
        )

        assert gate.questions == {}
        assert len(gate.earlier[("agentic-ai.1", "Who holds the old keys?")]) == 3
        assert "agentic-ai.1" in gate.no_evidence

    def test_dormant_questions_have_no_evidence(self):
        gate = evidence_gate([_ledger("2026-W37", _entry("physical-ai.1"))], THEMES)

        assert gate.no_evidence == ["agentic-ai.1", "physical-ai.2"]

    def test_most_evidence_first(self):
        gate = evidence_gate(
            _month(
                *_recurring("agentic-ai.1"),
                *_recurring("physical-ai.2", ("2026-W36", "2026-W37", "2026-W38", "2026-W39")),
                *_recurring("physical-ai.1", ("2026-W36", "2026-W37", "2026-W38")),
            ),
            THEMES,
        )

        assert list(gate.questions) == ["physical-ai.2", "physical-ai.1", "agentic-ai.1"]

    def test_new_topics_qualify_by_signals_or_convergence(self):
        gate = evidence_gate(
            _month(
                *_recurring("NEW", cluster_id="thrice", early=True),
                *_recurring("NEW", ("2026-W36", "2026-W37"), cluster_id="twice", early=True),
                *_recurring("NEW", ("2026-W36", "2026-W37"), cluster_id="converged", status="candidate-trend"),
                ("2026-W37", _entry("NEW", cluster_id="converged-once", status="candidate-trend")),
            ),
            THEMES,
        )

        assert list(gate.topics) == ["thrice", "converged"]


class TestMonthlyCompose:
    MONTH = "2026-09"

    def _compose(self, gate, digest):
        material = monthly_material(THEMES, gate)
        return compose_monthly_markdown(self.MONTH, THEMES, gate, digest, material, []), material

    def test_answer_for_an_unqualified_question(self, caplog):
        gate = evidence_gate(_month(*_recurring("physical-ai.1")), THEMES)
        digest = MonthlyDigest(
            bottom_line="Robots get paid.",
            answers=[
                QuestionAnswer(
                    question="physical-ai.1", lean="yes", evidence="Paid [pilots](F1).", for_2027="P.", still_open="O."
                ),
                QuestionAnswer(
                    question="agentic-ai.1", lean="users", evidence="Invented.", for_2027="P.", still_open="O."
                ),
            ],
        )

        markdown, _ = self._compose(gate, digest)

        assert "### Paid work?" in markdown
        assert "_Physical AI · yes · 3 signals in 2 weeks_" in markdown
        assert "Paid [pilots](https://x/1)." in markdown
        assert "Invented" not in markdown and "### Who holds the keys?" not in markdown
        assert "dropped answer for unqualified or repeated 'agentic-ai.1'" in caplog.text

    def test_counts_and_order_from_code(self):
        gate = evidence_gate(
            _month(*_recurring("agentic-ai.1"), *_recurring("physical-ai.2", ("2026-W36", "2026-W37", "2026-W38"))),
            THEMES,
        )
        answers = [
            QuestionAnswer(question=qid, lean="x", evidence="E.", for_2027="P.", still_open="O.")
            for qid in ("agentic-ai.1", "physical-ai.2")
        ]

        markdown, _ = self._compose(gate, MonthlyDigest(bottom_line="B.", answers=answers))

        assert markdown.index("### On site?") < markdown.index("### Who holds the keys?")
        assert "_Physical AI · x · 3 signals in 3 weeks_" in markdown

    def test_qualifying_question_left_unanswered_keeps_its_signals(self):
        gate = evidence_gate(_month(*_recurring("physical-ai.1", text="Robots [paid](https://x/p).")), THEMES)

        markdown, _ = self._compose(gate, MonthlyDigest(bottom_line="B."))

        assert "_Physical AI · 3 signals in 2 weeks_" in markdown
        assert "- 2026-W37: Robots [paid](https://x/p)." in markdown

    def test_new_topic_with_a_question_to_add(self):
        gate = evidence_gate(
            _month(*_recurring("NEW", ("2026-W36", "2026-W37"), cluster_id="c", status="candidate-trend")), THEMES
        )
        digest = MonthlyDigest(
            bottom_line="B.",
            new_topics=[
                NewTopic(topic="T1", title="Robot fleets", evidence="Fleets [grew](F1).", proposed_question="Q?")
            ],
        )

        markdown, material = self._compose(gate, digest)

        assert material.topics == {"T1": "c"}
        section = markdown.split("## New for the board")[1]
        assert "### Robot fleets" in section
        assert "_Physical AI · 2 signals in 2 weeks · candidate trend_" in section
        assert "**A question to add:** Q?" in section

    def test_thin_no_evidence_and_earlier_questions(self):
        gate = evidence_gate(
            [
                _ledger("2026-W36", _entry("physical-ai.1", early=True, title="Robot pilot")),
                _ledger("2026-W37", _entry("agentic-ai.1", question="Who holds the old keys?")),
            ],
            THEMES,
        )

        markdown, _ = self._compose(gate, None)

        thin = markdown.split("## Thin evidence")[1].split("## No evidence")[0]
        assert "- **Physical AI:** Paid work? (1 signal in 1 week)" in thin
        assert "Robot pilot" not in thin
        assert "- **Agentic AI:** Who holds the keys?" in markdown
        assert "- **Physical AI:** On site?" in markdown
        assert '- "Who holds the old keys?" (agentic-ai.1): 1 signal in 1 week' in markdown

    def test_material_cites_by_key_only_qualifying_evidence(self):
        gate = evidence_gate(
            _month(
                *_recurring("physical-ai.1", text="A [first](https://x/a) and [b](https://x/b)."),
                ("2026-W37", _entry("physical-ai.2", early=True, text="Thin [c](https://x/c).")),
            ),
            THEMES,
        )

        material = monthly_material(THEMES, gate)

        assert "QUESTION physical-ai.1 (line: Physical AI): Paid work?" in material.text
        assert "  - W36 (strengthening; lean: moving) Title: A [first](F1) and [b](F2)." in material.text
        assert "https://" not in material.text and "2026-W" not in material.text
        assert "physical-ai.2" not in material.text
        assert material.refs == {"F1": "https://x/a", "F2": "https://x/b"}


class TestMonthlyModel:
    def test_ids_restricted_to_qualifying_ones(self):
        from pydantic import ValidationError

        schema = monthly_model(["physical-ai.1"], ["T1"])
        answer = {"lean": "x", "evidence": "E.", "for_2027": "P.", "still_open": "O."}

        schema(bottom_line="B.", answers=[{"question": "physical-ai.1", **answer}])
        with pytest.raises(ValidationError):
            schema(bottom_line="B.", answers=[{"question": "Paid work?", **answer}])


@pytest.fixture(autouse=True)
def _setup(data_dir, monkeypatch):
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.DATA_DIR", data_dir)
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.HIPEAC_VISION_BOARD_EMAIL", "news@example.com")
    monkeypatch.setattr("hipeac_agents.agents.vision_watch.settings.AGENTMAIL_INBOX_VISION_WATCH", "vision-news")


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM(
        {
            MonthlyDigest: MonthlyDigest(
                bottom_line="Personal orchestrators moved from demos to first products.",
                answers=[
                    QuestionAnswer(
                        question="next-computing-paradigm.1",
                        lean="first products",
                        evidence="Two launches [shipped](F1).",
                        for_2027="Orchestrators are arriving.",
                        still_open="Who runs them.",
                    )
                ],
            )
        }
    )


def _write_ledgers() -> None:
    question = "Are personal AI orchestrators emerging?"
    for week in ("2026-W36", "2026-W37", "2026-W38"):
        workspace.write_weekly_ledger(
            LedgerFile(
                week=week,
                created=date(2026, 9, 29),
                entries=[
                    LedgerEntry(
                        question_id="next-computing-paradigm.1",
                        question=question,
                        lean="first products",
                        theme="next-computing-paradigm",
                        cluster_id="orchestrators",
                        status="emerging",
                        early=True,
                        title="An orchestrator ships",
                        text="An orchestrator [shipped](https://example.com/a).",
                    )
                ],
            )
        )


def _state(send: bool) -> VisionWatchState:
    return VisionWatchState.model_construct(week="2026-W39", month="2026-09", send=send)


class TestMonthlyNode:
    async def test_one_call_on_the_qualifying_questions(self, llm):
        _write_ledgers()

        updates = await monthly_node_mod.monthly_node(
            _state(False), services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        assert len(llm.calls) == 1
        schema, prompt = llm.calls[0]
        assert issubclass(schema, MonthlyDigest)
        assert "QUESTION next-computing-paradigm.1" in prompt
        markdown = updates["digest_markdown"]
        assert "_next-computing-paradigm · first products · 3 signals in 3 weeks_" in markdown
        assert "Two launches [shipped](https://example.com/a)." in markdown
        assert "no ledger for 2026-W39" in markdown
        assert workspace.read_monthly_digest("2026-09") == markdown

    async def test_nothing_qualifies(self, llm):
        updates = await monthly_node_mod.monthly_node(
            _state(False), services=Services(crawl=None, mail=None, vision=None), llm=llm
        )

        assert not llm.calls
        markdown = updates["digest_markdown"]
        assert NOTHING_QUALIFIES in markdown
        assert "## No evidence this month" in markdown


class TestMonthlySend:
    async def test_composed_month_is_sendable_later_exactly_once(self, llm):
        """Regression (baseline B1): a month composed without ``--send`` could
        never be sent — the recorded-digest replay returned before the send."""
        _write_ledgers()
        mail = FakeMail()
        services = Services(crawl=None, mail=mail, vision=None)

        await monthly_node_mod.monthly_node(_state(False), services=services, llm=llm)
        assert not mail.sent
        llm.calls.clear()

        first = await monthly_node_mod.monthly_node(_state(True), services=services, llm=llm)
        second = await monthly_node_mod.monthly_node(_state(True), services=services, llm=llm)

        assert first["digest_sent"] is True
        assert second["digest_sent"] is False
        assert len(mail.sent) == 1
        assert mail.sent[0][2] == "Personal orchestrators moved from demos to first products."
        assert not llm.calls

    async def test_sending_is_opt_in(self, llm):
        mail = FakeMail()

        updates = await monthly_node_mod.monthly_node(
            _state(False), services=Services(crawl=None, mail=mail, vision=None), llm=llm
        )

        assert updates["digest_sent"] is False
        assert not mail.sent
        assert "## Bottom line" in updates["digest_markdown"]
