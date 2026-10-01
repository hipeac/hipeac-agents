"""The harvest node's LLM runner wrappers.

One method per judgement call; each pairs the prompt from ``prompts.py`` with
the structured-output model from ``models.py``. Calls are throttled through a
shared semaphore and retried with backoff on rate-limit errors — a full week
of sources fires many calls at once.
"""

import asyncio
from typing import Any

from hipeac_agents.agents.vision_watch import schemas

from . import prompts
from .models import CandidateList, GateBatch, GateVerdict, NearMatchGroups, NotableSelection, TriageVerdict


# Cap on page markdown fed to the extraction call — listing pages can be
# tens of kilobytes and the relevant items sit near the top.
EXTRACTION_INPUT_CHARS = 12_000

# Candidates per triage call: large enough for one call per typical source,
# small enough that no decision gets lost in a long list.
TRIAGE_BATCH = 40

# Titles per notable-selection call: titles are short, so a long list fits.
SELECT_BATCH = 100

# Candidates per verdict call: the theme list is sent once per batch, not
# once per candidate; small enough that each still gets a careful verdict.
VERDICT_BATCH = 8


class HarvestContext:
    """Per-run helpers the harvest node passes around."""

    def __init__(self, llm: Any, max_concurrent: int = 6) -> None:
        """Hold the LLM structured-output runners for the judgement calls.

        :param llm: The chat model; wrapped per call via ``with_structured_output``.
        :param max_concurrent: Ceiling on in-flight LLM calls for this run.
        """
        self._llm = llm
        self._semaphore = asyncio.Semaphore(max_concurrent)
        # arXiv answers a burst from one client with errors: its categories are
        # harvested concurrently, so their requests queue here, one at a time.
        self.arxiv_slot = asyncio.Lock()

    async def _invoke(self, schema: type, prompt: str) -> Any:
        """Run one structured-output call, throttled, with backoff on rate limits.

        :param schema: The structured-output model the call must produce.
        :param prompt: The full prompt text.
        :returns: The parsed model instance.
        """
        runner = self._llm.with_structured_output(schema)

        for attempt in range(5):
            try:
                async with self._semaphore:
                    return await runner.ainvoke(prompt)
            except Exception as exc:
                if attempt == 4:
                    raise
                if "RateLimit" not in type(exc).__name__ and "429" not in str(exc):
                    raise
                await asyncio.sleep(5 * (attempt + 1))

        raise RuntimeError("unreachable")

    async def extract_candidates(self, text: str) -> CandidateList:
        """Extract candidate developments from one page or newsletter body.

        LLM judgement call (candidate extraction) — see ``prompts.CANDIDATE_EXTRACTION``.
        """
        prompt = prompts.CANDIDATE_EXTRACTION + "\n\nPage content:\n" + text[:EXTRACTION_INPUT_CHARS]
        return await self._invoke(CandidateList, prompt)

    async def triage(self, items: list[tuple[str, str]], themes: list[schemas.ThemeDef]) -> set[int]:
        """Decide which candidates could be a signal for a theme, in batches.

        LLM judgement call (triage) — see ``prompts.TRIAGE``. A candidate the
        model leaves out of its answer is kept: dropping is the decision that
        must be explicit.

        :param items: ``(title, summary)`` per candidate.
        :param themes: The themes.
        :returns: The indices of the candidates to keep.
        """
        questions = "\n".join(t.outline() for t in themes)
        kept: set[int] = set()
        for offset in range(0, len(items), TRIAGE_BATCH):
            batch = items[offset : offset + TRIAGE_BATCH]
            lines = "\n".join(f"{i}. {title} — {summary[:300]}" for i, (title, summary) in enumerate(batch))
            verdict = await self._invoke(
                TriageVerdict,
                prompts.TRIAGE + f"\n\nThemes:\n{questions}\n\nCandidates:\n{lines}",
            )
            dropped = {item.index for item in verdict.items if not item.keep}
            kept.update(offset + i for i in range(len(batch)) if i not in dropped)
        return kept

    async def select_notable(
        self, items: list[tuple[str, str]], themes: list[schemas.ThemeDef], budget: int
    ) -> list[int]:
        """Pick at most ``budget`` notable items from a long list, most notable first.

        LLM judgement call (notable selection) — see ``prompts.SELECT_NOTABLE``.
        Long lists are screened in batches, each keeping at most ``budget``,
        then the survivors compete in one final pick. Numbers the model
        invents are ignored, and the budget is enforced.

        :param items: ``(title, summary)`` per item.
        :param themes: The themes.
        :param budget: The most items to keep.
        :returns: The selected indices, most notable first.
        """
        if not items:
            return []

        themes_text = "\n".join(t.outline() for t in themes)

        async def pick(indices: list[int]) -> list[int]:
            lines = "\n".join(
                f"{n}. {items[i][0]}" + (f" — {items[i][1][:200]}" if items[i][1] else "")
                for n, i in enumerate(indices)
            )
            prompt = prompts.SELECT_NOTABLE.format(budget=budget) + f"\n\nThemes:\n{themes_text}\n\nItems:\n{lines}"
            chosen = (await self._invoke(NotableSelection, prompt)).indices
            picked = [indices[n] for n in dict.fromkeys(chosen) if 0 <= n < len(indices)]
            return picked[:budget]

        pool = list(range(len(items)))
        while len(pool) > SELECT_BATCH:
            survivors: list[int] = []
            for offset in range(0, len(pool), SELECT_BATCH):
                survivors.extend(await pick(pool[offset : offset + SELECT_BATCH]))
            pool = survivors
        return await pick(pool)

    async def gate_candidate(
        self,
        item_title: str,
        item_summary: str,
        page_title: str,
        themes: list[schemas.ThemeDef],
        tip: bool = False,
    ) -> GateVerdict:
        """Run the merged verification gate for one candidate.

        LLM judgement call (verification gate) — see ``prompts.GATE``.

        :param item_title: The candidate's claimed headline.
        :param item_summary: The candidate's summary.
        :param page_title: The actual title of the fetched page.
        :param themes: The watched themes.
        :returns: The gate verdict: theme ids, significance, datapoint, title match.
        """
        questions = "\n".join(t.brief() for t in themes)

        tip_suffix = (
            "\n\nThis candidate is a board tip a human editor flagged. If it fits no "
            "theme, still return the single closest theme id in theme_ids: a tip is "
            "never off-theme."
            if tip
            else ""
        )

        return await self._invoke(
            GateVerdict,
            prompts.GATE
            + f"\n\nThemes:\n{questions}"
            + f"\n\nClaimed headline: {item_title}\nClaimed summary: {item_summary}\nActual page title: {page_title}"
            + tip_suffix,
        )

    async def gate_batch(self, items: list[tuple[str, str, str]], themes: list[schemas.ThemeDef]) -> list[GateVerdict]:
        """Judge several candidates, ``VERDICT_BATCH`` per call.

        LLM judgement call (verification gate) — see ``prompts.GATE``. A lone
        candidate gets the single-candidate call; a candidate the model leaves
        out of a batch answer is judged again on its own, so every candidate
        gets exactly one verdict.

        :param items: ``(claimed headline, claimed summary, actual page title)`` per candidate.
        :param themes: The themes.
        :returns: One verdict per item, in order.
        """
        if len(items) == 1:
            return [await self.gate_candidate(*items[0], themes)]

        questions = "\n".join(t.brief() for t in themes)
        verdicts: list[GateVerdict | None] = [None] * len(items)

        for offset in range(0, len(items), VERDICT_BATCH):
            batch = items[offset : offset + VERDICT_BATCH]
            listing = "\n\n".join(
                f"Candidate {i}:\nClaimed headline: {title}\nClaimed summary: {summary}\nActual page title: {page}"
                for i, (title, summary, page) in enumerate(batch)
            )
            answer = await self._invoke(
                GateBatch,
                prompts.GATE
                + f"\n\nThemes:\n{questions}"
                + "\n\nReturn one verdict per candidate below, with its number as index."
                + f"\n\n{listing}",
            )
            for verdict in answer.verdicts:
                if 0 <= verdict.index < len(batch) and verdicts[offset + verdict.index] is None:
                    verdicts[offset + verdict.index] = GateVerdict.model_validate(verdict.model_dump(exclude={"index"}))

        for i, verdict in enumerate(verdicts):
            if verdict is None:
                verdicts[i] = await self.gate_candidate(*items[i], themes)
        return verdicts

    async def near_match_groups(self, items: list[tuple[str, str]]) -> NearMatchGroups:
        """Group finding ids that are the same underlying event.

        LLM judgement call (near-match rule) — see ``prompts.NEAR_MATCH``.
        """
        lines = "\n".join(f"- {finding_id}: {title}" for finding_id, title in items)
        return await self._invoke(NearMatchGroups, prompts.NEAR_MATCH + "\n\nFindings:\n" + lines)
