"""Digest node: composes the weekly pulse from the cluster logs and sends it.

Weekly digest only — the monthly synthesis belongs to a future agent. Layout:

- ``prompts.py`` — the LLM prompt constants.
- ``models.py`` — the structured-output models for the judgement calls.
- ``node.py`` — orchestration: prose calls, markdown assembly, write, send.

LLM-JUDGEMENT CALLS — review before the first live run:

1. ``DigestProse`` / ``DIGEST_ITEM`` — item prose in the documented anatomy.
2. ``DIGEST_IN_BRIEF`` — the ~100-word In brief section.
3. ``SignalGroups`` / ``DIGEST_SIGNALS`` — grouping off-theme rejects into an
   "Also worth watching" signal, when a coherent group exists.

Boundaries: reads clusters, findings, rejects, last digest; writes only the
digest; recommends, never decides. AgentMail send is its only service call.
"""

from .models import DigestProse, SignalGroup, SignalGroups  # noqa: F401
from .node import compose_digest_markdown, digest_node  # noqa: F401


__all__ = ["DigestProse", "SignalGroup", "SignalGroups", "compose_digest_markdown", "digest_node"]
