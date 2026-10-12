"""Digest node: composes the weekly digest from the cluster logs and sends it.

Layout:

- ``prompts.py`` — the prompts for the judgement calls: the digest, a
  recorded week's bottom line rewritten on its own (``--intro-only``), and a
  light copy-edit of its story prose (``--edit``).
- ``models.py`` — their structured-output models.
- ``node.py`` — orchestration: story selection, the prose call, citation
  resolution and the budget, markdown assembly, write, send.

Per theme, the digest tells at most two stories and lists the other
candidates as one-line items, each tagged with the open question it moves;
findings are cited by id, and code turns citations into links, so no URL the
model invents is ever published. The ledger (every printed item) and the
signals log (every finding) are written beside it.
"""

from .models import DigestItem, EditedDigest, WeeklyDigest, WeeklyIntro  # noqa: F401
from .node import (  # noqa: F401
    check_edited_digest,
    compose_digest_markdown,
    digest_node,
    edit_node,
    intro_node,
    replace_bottom_line,
    resolve_citations,
)


__all__ = [
    "DigestItem",
    "EditedDigest",
    "WeeklyDigest",
    "WeeklyIntro",
    "check_edited_digest",
    "compose_digest_markdown",
    "digest_node",
    "edit_node",
    "intro_node",
    "replace_bottom_line",
    "resolve_citations",
]
