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
from .models import CandidateList, GateVerdict, NearMatchGroups, TriageVerdict


# Cap on page markdown fed to the extraction call — listing pages can be
# tens of kilobytes and the relevant items sit near the top.
EXTRACTION_INPUT_CHARS = 12_000

# Candidates per triage call: large enough for one call per typical source,
# small enough that no decision gets lost in a long list.
TRIAGE_BATCH = 40


class HarvestContext:
    """Per-run helpers the harvest node passes around."""

    def __init__(self, llm: Any, max_concurrent: int = 6) -> None:
        """Hold the LLM structured-output runners for the judgement calls.

        :param llm: The chat model; wrapped per call via ``with_structured_output``.
        :param max_concurrent: Ceiling on in-flight LLM calls for this run.
        """
        self._llm = llm
        self._semaphore = asyncio.Semaphore(max_concurrent)

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
        """Decide which candidates could move a watch question, in batches.

        LLM judgement call (triage) — see ``prompts.TRIAGE``. A candidate the
        model leaves out of its answer is kept: dropping is the decision that
        must be explicit.

        :param items: ``(title, summary)`` per candidate.
        :param themes: The watch questions.
        :returns: The indices of the candidates to keep.
        """
        questions = "\n".join(t.brief() for t in themes)
        kept: set[int] = set()
        for offset in range(0, len(items), TRIAGE_BATCH):
            batch = items[offset : offset + TRIAGE_BATCH]
            lines = "\n".join(f"{i}. {title} — {summary[:300]}" for i, (title, summary) in enumerate(batch))
            verdict = await self._invoke(
                TriageVerdict,
                prompts.TRIAGE + f"\n\nWatch questions:\n{questions}\n\nCandidates:\n{lines}",
            )
            dropped = {item.index for item in verdict.items if not item.keep}
            kept.update(offset + i for i in range(len(batch)) if i not in dropped)
        return kept

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
        :returns: The gate verdict: theme ids, tier, datapoint, title match.
        """
        questions = "\n".join(t.brief() for t in themes)

        tip_suffix = (
            "\n\nThis candidate is a board tip a human editor flagged. If it moves no "
            "watch question, still return the single closest question id in theme_ids: "
            "a tip is never off-theme."
            if tip
            else ""
        )

        return await self._invoke(
            GateVerdict,
            prompts.GATE
            + f"\n\nWatch questions:\n{questions}"
            + f"\n\nClaimed headline: {item_title}\nClaimed summary: {item_summary}\nActual page title: {page_title}"
            + tip_suffix,
        )

    async def near_match_groups(self, items: list[tuple[str, str]]) -> NearMatchGroups:
        """Group finding ids that are the same underlying event.

        LLM judgement call (near-match rule) — see ``prompts.NEAR_MATCH``.
        """
        lines = "\n".join(f"- {finding_id}: {title}" for finding_id, title in items)
        return await self._invoke(NearMatchGroups, prompts.NEAR_MATCH + "\n\nFindings:\n" + lines)
