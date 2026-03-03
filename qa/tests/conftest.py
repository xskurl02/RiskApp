from __future__ import annotations

import sys
from pathlib import Path

# Tests live outside of client/server by design.
# Make both packages importable without requiring editable installs.
ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "server", ROOT / "client"):
    s = str(_p)
    if s not in sys.path:
        sys.path.insert(0, s)
