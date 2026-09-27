"""Model tiers: configuration, defaults, parameters and usage reporting (no model is called)."""

import importlib

import pytest

from hipeac_agents import llms, settings


@pytest.fixture
def reload_settings(monkeypatch):
    yield lambda: importlib.reload(settings)
    monkeypatch.undo()
    importlib.reload(settings)


def test_tiers_read_their_own_settings(monkeypatch, reload_settings):
    monkeypatch.setenv("LLM_SMALL_MODEL", "tiny")
    monkeypatch.setenv("LLM_SMALL_REASONING", "")
    monkeypatch.setenv("LLM_BASE_MODEL", "mid")
    monkeypatch.setenv("LLM_THINKING_MODEL", "big")
    monkeypatch.setenv("LLM_THINKING_REASONING", "high")
    reload_settings()

    assert llms.tiers() == {
        "small": llms.Tier("tiny", ""),
        "base": llms.Tier("mid", "low"),
        "thinking": llms.Tier("big", "high"),
    }


def test_defaults_follow_the_gpt_6_lineup_and_old_names_are_ignored(monkeypatch, reload_settings):
    """Regression: the old per-task names put the harvest on the big model."""
    for name in ("SMALL", "BASE", "THINKING"):
        monkeypatch.delenv(f"LLM_{name}_MODEL", raising=False)
        monkeypatch.delenv(f"LLM_{name}_REASONING", raising=False)
    monkeypatch.setenv("OPENAI_JUDGEMENT_MODEL", "gpt-5.6-luna")
    reload_settings()

    assert {name: str(tier) for name, tier in llms.tiers().items()} == {
        "small": "gpt-6-luna (reasoning: none)",
        "base": "gpt-6-sol (reasoning: low)",
        "thinking": "gpt-6-astra (reasoning: low)",
    }


@pytest.mark.parametrize(
    ("reasoning", "expected"),
    [
        ("none", {"reasoning_effort": "none", "temperature": 0}),
        ("low", {"reasoning_effort": "low"}),
        ("", {"temperature": 0}),
    ],
)
def test_temperature_only_without_reasoning(reasoning, expected):
    """Reasoning models reject ``temperature`` unless reasoning is off."""
    assert llms.model_kwargs(llms.Tier("m", reasoning)) == expected


def test_usage_lines_rank_models_by_input_tokens():
    usage = {
        "luna": {"input_tokens": 9_000, "output_tokens": 700},
        "mini": {"input_tokens": 800_000, "output_tokens": 40_000},
    }

    assert llms.usage_lines(usage) == [
        "  mini: 800,000 tokens in, 40,000 out",
        "  luna: 9,000 tokens in, 700 out",
    ]


def test_usage_lines_show_cached_input_and_reasoning_output():
    usage = {
        "gpt-6-sol": {
            "input_tokens": 12_000,
            "output_tokens": 900,
            "input_token_details": {"cache_read": 8_000},
            "output_token_details": {"reasoning": 600},
        }
    }

    assert llms.usage_lines(usage) == ["  gpt-6-sol: 12,000 tokens in (8,000 cached), 900 out (600 reasoning)"]
