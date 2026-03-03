"""Allow `python -m riskapp_server` for local development."""

from __future__ import annotations

import os


def main() -> int:
    # Lazy import so this file stays importable even if uvicorn isn't installed.
    import uvicorn  # type: ignore

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("riskapp_server.main.app:app", host=host, port=port, reload=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
