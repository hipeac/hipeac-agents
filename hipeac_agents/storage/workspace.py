"""Generic filesystem primitives for workspace files.

The only module in the collection that touches the filesystem data directory
directly. It knows nothing about any agent's domain: agents map their schemas,
folder maps, and write-once / append-only rules onto these primitives from
their own ``workspace.py`` (e.g. ``hipeac_agents.agents.vision_watch.workspace``).
"""

import json
from pathlib import Path
from typing import Any

import yaml


class WorkspaceError(Exception):
    """Raised when a storage rule (write-once, append-only) is violated."""


def write_once(path: Path, content: str) -> Path:
    """Create a write-once file, raising if it already exists.

    :param path: Destination path; parent directories are created as needed.
    :param content: Full file content.
    :returns: The written path.
    :raises WorkspaceError: If the file already exists (write-once violation).
    """
    if path.exists():
        raise WorkspaceError(f"write-once violation: {path} already exists")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def read_json(path: Path) -> dict[str, Any]:
    """Read and parse a JSON workspace file.

    :param path: The file to read.
    :returns: The parsed document.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a YAML workspace file.

    :param path: The file to read.
    :returns: The parsed document.
    """
    return yaml.safe_load(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
