"""Digest node: composes the weekly digest from the cluster logs and sends it.

Layout:

- ``prompts.py`` — the prompt for the one judgement call.
- ``models.py`` — its structured-output model.
- ``node.py`` — orchestration: story selection, the prose call, citation
  resolution and the budget, markdown assembly, write, send.

The digest tells at most two stories per theme, citing findings by id; code
turns citations into links, so no URL the model invents is ever published.
Every finding of the week is kept in the signals log written beside it.
"""

from .models import Story, StoryDigest  # noqa: F401
from .node import compose_digest_markdown, digest_node, resolve_citations  # noqa: F401


__all__ = ["Story", "StoryDigest", "compose_digest_markdown", "digest_node", "resolve_citations"]
