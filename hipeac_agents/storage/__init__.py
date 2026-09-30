"""Generic storage primitives shared by all agents.

Only ``storage.workspace`` touches the filesystem; per-agent ``workspace``
modules map their schemas and folders onto these primitives.
"""

from .workspace import WorkspaceError, write_once  # noqa: F401


__all__ = ["WorkspaceError", "write_once"]
