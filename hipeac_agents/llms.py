"""The chat models every agent can use, by capability tier.

- ``small``: cheap and fast, for high-volume classification (thousands of calls).
- ``base``: the everyday model, for judgement that needs more context.
- ``thinking``: the strongest model, for the few calls whose output people read.

Models are configured by tier (``LLM_<TIER>_MODEL``, ``LLM_<TIER>_REASONING``),
never by task, so agents share one vocabulary.
"""

from dataclasses import dataclass
from typing import Any

from hipeac_agents import settings


@dataclass(frozen=True)
class Tier:
    """One tier's configuration: the model and its reasoning effort ("" sends none)."""

    model: str
    reasoning: str

    def __str__(self) -> str:
        return f"{self.model} (reasoning: {self.reasoning})" if self.reasoning else self.model


@dataclass(frozen=True)
class Models:
    """The chat models a run was wired with, one per tier."""

    small: Any
    base: Any
    thinking: Any


def tiers() -> dict[str, Tier]:
    """Read the configuration of each tier.

    :returns: Tier name to its model and reasoning effort.
    """
    return {
        "small": Tier(settings.LLM_SMALL_MODEL, settings.LLM_SMALL_REASONING),
        "base": Tier(settings.LLM_BASE_MODEL, settings.LLM_BASE_REASONING),
        "thinking": Tier(settings.LLM_THINKING_MODEL, settings.LLM_THINKING_REASONING),
    }


def model_kwargs(tier: Tier) -> dict[str, Any]:
    """Build the model parameters for a tier.

    Temperature 0 keeps verdicts reproducible, but reasoning models reject
    ``temperature`` unless reasoning is off (``none``); some, such as
    ``gpt-6-astra``, cannot turn it off at all.

    :param tier: The tier's configuration.
    :returns: Keyword arguments for the chat model.
    """
    kwargs: dict[str, Any] = {}
    if tier.reasoning:
        kwargs["reasoning_effort"] = tier.reasoning
    if tier.reasoning in ("", "none"):
        kwargs["temperature"] = 0
    return kwargs


def load_models() -> Models:
    """Build the chat model of each tier.

    :returns: The models, one per tier.
    """
    from langchain.chat_models import init_chat_model

    def build(tier: Tier) -> Any:
        return init_chat_model(tier.model, model_provider=settings.LLM_PROVIDER, **model_kwargs(tier))

    configured = tiers()
    return Models(
        small=build(configured["small"]), base=build(configured["base"]), thinking=build(configured["thinking"])
    )


def usage_lines(usage: dict[str, Any]) -> list[str]:
    """Render a run's token usage per model, for the run summary.

    Output tokens include any reasoning tokens, which are billed as output.

    :param usage: Model name to its usage metadata (``input_tokens``, ``output_tokens``).
    :returns: One line per model, most input tokens first.
    """
    rows = sorted(usage.items(), key=lambda item: -(item[1].get("input_tokens") or 0))
    return [
        f"  {name}: {meta.get('input_tokens') or 0:,} tokens in, {meta.get('output_tokens') or 0:,} out"
        for name, meta in rows
    ]
