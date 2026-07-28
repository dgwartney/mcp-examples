#!/usr/bin/env python3
"""
Backward-compatible wrapper around ``mcp-server-kit add-server``.

Usage:
    uv run python scripts/new_server.py <Name>

This delegates to :func:`mcp_server_kit.scaffold.add_server`, which generates a
new server module + test in this repo and registers it in ``combined.py`` and
``__init__.py``. Prefer the console entry point directly:

    mcp-server-kit add-server <Name>

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import sys
from pathlib import Path

# Ensure the repo root is importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server_kit.scaffold import add_server  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print(f"Usage: uv run python {Path(__file__).name} <Name>", file=sys.stderr)
        sys.exit(1)
    add_server(sys.argv[1])


if __name__ == "__main__":
    main()
