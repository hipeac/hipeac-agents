"""Environment-driven configuration for the agent collection.

Collection-wide settings only: service keys, the LLM provider, Sentry.
Per-agent settings (data directory, mailboxes) live in each agent's own
``settings.py`` — e.g. ``hipeac_agents.agents.vision_watch.settings``.

Services are independently configurable and skippable:

- ``crawl`` and ``mail`` use plain provider APIs via their official Python
  SDKs (Firecrawl, AgentMail) — no MCP overhead. An unset API key means the
  service is skipped.
- ``vision`` is the one MCP-backed service (``hipeac-mcp`` only speaks MCP).
  An unset URL means the service is skipped.

Nodes depend on the service protocols in ``hipeac_agents.services``, never on
providers directly, so a provider swap is a factory change only.
"""

import os


FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY") or None
FIRECRAWL_API_URL = os.environ.get("FIRECRAWL_API_URL", "https://api.firecrawl.dev")

AGENTMAIL_API_KEY = os.environ.get("AGENTMAIL_API_KEY") or None

HIPEAC_MCP_URL = os.environ.get("HIPEAC_MCP_URL") or None

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
# Three capability tiers, shared by every agent: a cheap small model for
# high-volume classification, a base model for everyday judgement, and a
# thinking model for the few calls whose output people read.
LLM_SMALL_MODEL = os.environ.get("LLM_SMALL_MODEL", "gpt-4o-mini")
LLM_BASE_MODEL = os.environ.get("LLM_BASE_MODEL", "gpt-5.6-luna")
LLM_THINKING_MODEL = os.environ.get("LLM_THINKING_MODEL") or LLM_BASE_MODEL

SENTRY_DSN = os.environ.get("SENTRY_DSN") or None
