"""The chat models every agent can use, by capability tier.

- ``small``: cheap and fast, for high-volume classification (thousands of calls).
- ``base``: the everyday model, for judgement that needs more context.
- ``thinking``: the strongest model, for the few calls whose output people read.

Models are configured by tier (``LLM_SMALL_MODEL``, ``LLM_BASE_MODEL``,
``LLM_THINKING_MODEL``), never by task, so agents share one vocabulary.
"""

from dataclasses import dataclass
from typing import Any

from hipeac_agents import settings


@dataclass(frozen=True)
class Models:
    """The chat models a run was wired with, one per tier."""

    small: Any
    base: Any
    thinking: Any


def model_names() -> dict[str, str]:
    """Name the configured model of each tier.

    :returns: Tier to model name.
    """
    return {"small": settings.LLM_SMALL_MODEL, "base": settings.LLM_BASE_MODEL, "thinking": settings.LLM_THINKING_MODEL}


def load_models() -> Models:
    """Build the chat model of each tier.

    Every tier runs at temperature 0: the same inputs must give the same
    verdicts, or recorded judgements stop being reproducible.

    :returns: The models, one per tier.
    """
    from langchain.chat_models import init_chat_model

    def build(name: str) -> Any:
        return init_chat_model(name, model_provider=settings.LLM_PROVIDER, temperature=0)

    names = model_names()
    return Models(small=build(names["small"]), base=build(names["base"]), thinking=build(names["thinking"]))


def usage_lines(usage: dict[str, Any]) -> list[str]:
    """Render a run's token usage per model, for the run summary.

    :param usage: Model name to its usage metadata (``input_tokens``, ``output_tokens``).
    :returns: One line per model, most input tokens first.
    """
    rows = sorted(usage.items(), key=lambda item: -(item[1].get("input_tokens") or 0))
    return [
        f"  {name}: {meta.get('input_tokens') or 0:,} tokens in, {meta.get('output_tokens') or 0:,} out"
        for name, meta in rows
    ]
