"""CLI entrypoint for ClawGuard."""

from __future__ import annotations

import sys


def serve() -> None:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is not installed. Run: pip install clawguard", file=sys.stderr)
        sys.exit(1)

    uvicorn.run("clawguard.server:app", host="127.0.0.1", port=8000, reload=False)
