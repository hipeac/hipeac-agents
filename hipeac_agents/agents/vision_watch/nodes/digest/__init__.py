"""Digest node: composes the weekly digest from the cluster logs and sends it.

Layout:

- ``prompts.py`` — the prompt for the one judgement call.
- ``models.py`` — its structured-output model.
- ``node.py`` — orchestration: story selection, the prose call, citation
  resolution and the budget, markdown assembly, write, send.

Per theme, the digest tells at most two stories and lists the other
candidates as one-line items, each tagged with the open question it moves;
findings are cited by id, and code turns citations into links, so no URL the
model invents is ever published. The ledger (every printed item) and the
signals log (every finding) are written beside it.
"""

from .models import DigestItem, WeeklyDigest  # noqa: F401
from .node import compose_digest_markdown, digest_node, resolve_citations  # noqa: F401


__all__ = ["DigestItem", "WeeklyDigest", "compose_digest_markdown", "digest_node", "resolve_citations"]
