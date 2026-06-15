r"""Entry point: \`python -m src.main\`.

Wraps the bootstrap in try/except so configuration errors (missing
required env vars, etc.) exit cleanly with a non-zero code and a
human-readable message.
"""

from __future__ import annotations

import asyncio
import sys

from src.app import start


async def _run() -> None:
    await start()
    # Keep the loop running forever; signal handlers stop it on shutdown.
    await asyncio.Event().wait()


def main() -> None:
    try:
        asyncio.run(_run())
    except OSError as exc:
        print(f"Environment error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
