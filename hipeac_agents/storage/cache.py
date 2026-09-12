"""Generic JSON file cache shared by the service layer.

Only ``storage`` touches the filesystem; providers use this to cache API
results keyed by a SHA-256 of their inputs, so repeated runs (and in-run
repeat fetches) don't pay for the same data twice.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def cache_key(kind: str, value: str) -> str:
    """Build a stable cache key from a kind and a value (e.g. a URL).

    :param kind: Namespace of the cached payload (e.g. ``"scrape"``).
    :param value: The value hashed into the key (e.g. the scraped URL).
    :returns: A hex digest like ``"scrape-<sha256>"``.
    """
    return f"{kind}-{hashlib.sha256(f'{kind}:{value}'.encode()).hexdigest()}"


def cache_dir(root: Path, kind: str) -> Path:
    """Return the cache directory for one kind of payload.

    :param root: The cache root directory.
    :param kind: Namespace of the payload.
    :returns: ``<root>/<kind>`` as a ``Path``.
    """
    return root / kind


def sharded_path(root: Path, kind: str, value: str) -> Path:
    """Return the cache file path for a value, sharded by the hash's first two letters.

    Keeps per-directory file counts low when the cache grows to thousands of
    entries: ``root/<kind>/<ab>/<kind>-<sha256>.json``.

    :param root: The cache root directory.
    :param kind: Namespace of the payload (e.g. ``"scrape"``).
    :param value: The value hashed into the key (e.g. the scraped URL).
    :returns: The shard path for the value.
    """
    key = cache_key(kind, value)
    digest = key.removeprefix(f"{kind}-")
    return cache_dir(root, kind) / digest[:2] / f"{key}.json"


def cache_get(path: Path) -> dict[str, Any] | None:
    """Read a cached payload.

    :param path: The cache file for the key.
    :returns: The stored payload, or ``None`` when nothing is cached.
    """
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None


def cache_put(path: Path, payload: dict[str, Any]) -> Path:
    """Store a payload, stamping when it was cached.

    :param path: The cache file for the key.
    :param payload: The JSON-serialisable payload.
    :returns: The written path.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"cached_at": datetime.now(UTC).isoformat(), "payload": payload}
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path
