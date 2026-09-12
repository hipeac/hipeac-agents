"""Allow ``./run python -m hipeac_agents <command>``."""

import asyncio

from hipeac_agents.cli import main


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
