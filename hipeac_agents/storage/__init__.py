"""Generic storage primitives shared by all agents.

Only ``storage.workspace`` touches the filesystem; per-agent ``workspace``
modules map their schemas and folders onto these primitives.
"""

from .workspace import (  # noqa: F401
    WorkspaceError,
    read_json,
    read_yaml,
    write_once,
)


__all__ = ["WorkspaceError", "read_json", "read_yaml", "write_once"]
