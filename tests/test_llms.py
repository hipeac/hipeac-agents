"""Model tiers: configuration, defaults and usage reporting (no model is called)."""

import importlib

from hipeac_agents import llms, settings


def test_tiers_read_their_own_settings(monkeypatch):
    monkeypatch.setenv("LLM_SMALL_MODEL", "tiny")
    monkeypatch.setenv("LLM_BASE_MODEL", "mid")
    monkeypatch.setenv("LLM_THINKING_MODEL", "big")
    importlib.reload(settings)
    try:
        assert llms.model_names() == {"small": "tiny", "base": "mid", "thinking": "big"}
    finally:
        monkeypatch.undo()
        importlib.reload(settings)


def test_thinking_falls_back_to_base_and_old_names_are_ignored(monkeypatch):
    """Regression: the old per-task names put the judgement role on the big model."""
    monkeypatch.delenv("LLM_SMALL_MODEL", raising=False)
    monkeypatch.delenv("LLM_THINKING_MODEL", raising=False)
    monkeypatch.setenv("LLM_BASE_MODEL", "mid")
    monkeypatch.setenv("OPENAI_JUDGEMENT_MODEL", "mid")
    importlib.reload(settings)
    try:
        assert llms.model_names() == {"small": "gpt-4o-mini", "base": "mid", "thinking": "mid"}
    finally:
        monkeypatch.undo()
        importlib.reload(settings)


def test_usage_lines_rank_models_by_input_tokens():
    usage = {
        "luna": {"input_tokens": 9_000, "output_tokens": 700},
        "mini": {"input_tokens": 800_000, "output_tokens": 40_000},
    }

    assert llms.usage_lines(usage) == [
        "  mini: 800,000 tokens in, 40,000 out",
        "  luna: 9,000 tokens in, 700 out",
    ]
