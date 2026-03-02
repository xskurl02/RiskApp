"""Apply SQL migration files using the app's DATABASE_URL.

Usage:
  python -m riskapp_server.ops.apply_sql riskapp_server/ops/sql/001_add_composite_indexes.sql

Notes:
  - This is intentionally tiny and dependency-free beyond SQLAlchemy.
  - For production, prefer a real migration tool (e.g., Alembic).
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, text


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "Usage: python -m riskapp_server.ops.apply_sql <file.sql>",
            file=sys.stderr,
        )
        return 2

    sql_path = Path(argv[1])
    if not sql_path.exists():
        print(f"SQL file not found: {sql_path}", file=sys.stderr)
        return 2

    # Import from the server package so env handling is consistent.
    from riskapp_server.core.config import DATABASE_URL

    engine = create_engine(DATABASE_URL)
    sql = sql_path.read_text(encoding="utf-8")

    with engine.begin() as conn:
        # Split on ';' to tolerate multi-statement files across drivers.
        for stmt in (s.strip() for s in sql.split(";") if s.strip()):
            conn.execute(text(stmt))
    print(f"Applied: {sql_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
