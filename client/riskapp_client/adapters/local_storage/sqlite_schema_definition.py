"""SQLite schema management.

Goals:
- Keep DDL/migrations readable and deterministic.
- Avoid try/except-driven migrations when we can cheaply introspect.
- Be safe to call repeatedly (idempotent).

This module is intentionally dependency-light and does not import LocalStore.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence

from riskapp_client.domain.scored_entity_fields import SCORED_ENTITY_META_SQLITE_COLUMNS


def _exec(conn: sqlite3.Connection, sql: str) -> None:
    """Internal helper for exec."""
    conn.execute(sql)


def _exec_many(conn: sqlite3.Connection, ddls: Iterable[str]) -> None:
    """Internal helper for exec many."""
    for ddl in ddls:
        _exec(conn, ddl)


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    # PRAGMA table_info returns rows: (cid, name, type, notnull, dflt_value, pk)
    """Internal helper for existing columns."""
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return {str(r[1]) for r in rows}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Internal helper for table exists."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,)
    ).fetchone()
    return bool(row)


def _has_fk_to_table(conn: sqlite3.Connection, table: str, *, ref_table: str) -> bool:
    """Internal helper for has fk to table."""
    try:
        rows = conn.execute(f"PRAGMA foreign_key_list({table});").fetchall()
    except sqlite3.Error:
        return False
    # PRAGMA foreign_key_list columns: (id, seq, table, from, to, on_update, on_delete, match)
    return any(str(r[2]) == ref_table for r in (rows or []))


def _migrate_assessments_table(conn: sqlite3.Connection) -> None:
    """Migrate legacy assessments schema that incorrectly FK'd to `risks`.

    Older versions stored opportunity assessments in the same table but had:
    - `risk_id TEXT NOT NULL`
    - `FOREIGN KEY(risk_id) REFERENCES risks(id)`

    With `PRAGMA foreign_keys=ON`, that makes opportunity assessments impossible.

    This migration:
    - drops the FK by rebuilding the table,
    - introduces `opportunity_id` (nullable),
    - keeps `risk_id` for backward compatibility (nullable).
    """
    # Disable FK checks during table rebuild.
    conn.execute("PRAGMA foreign_keys=OFF;")
    conn.execute("ALTER TABLE assessments RENAME TO assessments_old;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS assessments (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            risk_id TEXT,
            opportunity_id TEXT,
            item_id TEXT NOT NULL DEFAULT '',
            item_type TEXT NOT NULL DEFAULT 'risk',
            assessor_user_id TEXT NOT NULL DEFAULT '',
            probability INTEGER NOT NULL,
            impact INTEGER NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 0,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT '',
            dirty INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(project_id) REFERENCES projects(id)
        );
        """
    )
    old_cols = _existing_columns(conn, "assessments_old")
    select_cols = [
        c
        for c in (
            "id",
            "project_id",
            "risk_id",
            "item_id",
            "item_type",
            "assessor_user_id",
            "probability",
            "impact",
            "score",
            "notes",
            "version",
            "is_deleted",
            "updated_at",
            "dirty",
        )
        if c in old_cols
    ]
    if select_cols:
        rows = conn.execute(
            f"SELECT {', '.join(select_cols)} FROM assessments_old;"
        ).fetchall()
    else:
        rows = []

    def _row_get(row: sqlite3.Row, key: str, default=None):
        """Best-effort sqlite3.Row getter.

        sqlite3.Row is indexable by column name but doesn't implement .get.
        """
        try:
            return row[key]
        except Exception:
            return default

    for r in rows:
        # Resolve canonical target.
        item_id = str((r["item_id"] if "item_id" in old_cols else "") or "")
        if not item_id:
            item_id = str((r["risk_id"] if "risk_id" in old_cols else "") or "")
        item_type = str(
            (r["item_type"] if "item_type" in old_cols else "risk") or "risk"
        )
        item_type = item_type.strip().lower() or "risk"
        risk_id = item_id if item_type == "risk" else None
        opp_id = item_id if item_type == "opportunity" else None
        conn.execute(
            """
            INSERT INTO assessments (
                id, project_id, risk_id, opportunity_id, item_id, item_type,
                assessor_user_id, probability, impact, score, notes,
                version, is_deleted, updated_at, dirty
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                str(_row_get(r, "id", "")),
                str(_row_get(r, "project_id", "")),
                risk_id,
                opp_id,
                item_id,
                item_type,
                str(_row_get(r, "assessor_user_id", "")),
                int(_row_get(r, "probability", 1) or 1),
                int(_row_get(r, "impact", 1) or 1),
                int(_row_get(r, "score", 0) or 0),
                str(_row_get(r, "notes", "") or ""),
                int(_row_get(r, "version", 0) or 0),
                int(_row_get(r, "is_deleted", 0) or 0),
                str(_row_get(r, "updated_at", "") or ""),
                int(_row_get(r, "dirty", 0) or 0),
            ),
        )
    conn.execute("DROP TABLE assessments_old;")
    conn.execute("PRAGMA foreign_keys=ON;")


def ensure_columns(
    conn: sqlite3.Connection, table: str, columns: Sequence[tuple[str, str]]
) -> None:
    """Ensure the given columns exist on a table (best-effort).

    Notes:
    - SQLite supports adding columns via ALTER TABLE ... ADD COLUMN.
    - This is safe to run repeatedly.
    """
    existing = _existing_columns(conn, table)
    for name, col_type in columns:
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type};")


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create/upgrade schema for the local offline-first store."""
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    if _table_exists(conn, "assessments") and _has_fk_to_table(
        conn, "assessments", ref_table="risks"
    ):
        _migrate_assessments_table(conn)
    _exec_many(
        conn,
        [
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT ''
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS risks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                probability INTEGER NOT NULL,
                impact INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT '',
                dirty INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                probability INTEGER NOT NULL,
                impact INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT 0,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT '',
                dirty INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS actions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                risk_id TEXT,
                opportunity_id TEXT,

                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                owner_user_id TEXT,

                version INTEGER NOT NULL DEFAULT 0,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT '',
                dirty INTEGER NOT NULL DEFAULT 0
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                risk_id TEXT,
                opportunity_id TEXT,
                item_id TEXT NOT NULL DEFAULT '',
                item_type TEXT NOT NULL DEFAULT 'risk',
                assessor_user_id TEXT NOT NULL DEFAULT '',
                probability INTEGER NOT NULL,
                impact INTEGER NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 0,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT '',
                dirty INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id)
                -- NOTE: Do NOT FK to risks/opportunities; assessments can target either.
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                project_id TEXT PRIMARY KEY,
                last_server_time TEXT NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS outbox (
                change_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                entity TEXT NOT NULL,
                op TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                base_version INTEGER,
                record_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending', -- pending|blocked
                last_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            """,
        ],
    )
    ensure_columns(conn, "risks", SCORED_ENTITY_META_SQLITE_COLUMNS)
    ensure_columns(conn, "opportunities", SCORED_ENTITY_META_SQLITE_COLUMNS)
    ensure_columns(
        conn,
        "assessments",
        [
            ("item_id", "TEXT NOT NULL DEFAULT ''"),
            ("item_type", "TEXT NOT NULL DEFAULT 'risk'"),
            ("score", "INTEGER NOT NULL DEFAULT 0"),
            ("opportunity_id", "TEXT"),
        ],
    )
    _exec_many(
        conn,
        [
            "CREATE INDEX IF NOT EXISTS risks_project_idx ON risks(project_id, is_deleted, updated_at);",
            "CREATE INDEX IF NOT EXISTS opps_project_idx ON opportunities(project_id, is_deleted, updated_at);",
            "CREATE INDEX IF NOT EXISTS actions_project_idx ON actions(project_id, is_deleted, updated_at);",
            "CREATE INDEX IF NOT EXISTS outbox_pending_idx ON outbox(project_id, status, created_at);",
            "CREATE INDEX IF NOT EXISTS outbox_entity_idx ON outbox(project_id, entity, entity_id);",
            "CREATE INDEX IF NOT EXISTS assessments_item_idx ON assessments(project_id, item_id, item_type, is_deleted);",
            "CREATE INDEX IF NOT EXISTS assessments_risk_idx ON assessments(project_id, risk_id, is_deleted);",
            "CREATE INDEX IF NOT EXISTS assessments_opp_idx ON assessments(project_id, opportunity_id, is_deleted);",
            "CREATE INDEX IF NOT EXISTS assessments_user_idx ON assessments(project_id, assessor_user_id);",
            "CREATE UNIQUE INDEX IF NOT EXISTS risks_project_code_uq ON risks(project_id, code);",
            "CREATE UNIQUE INDEX IF NOT EXISTS opps_project_code_uq ON opportunities(project_id, code);",
        ],
    )
    conn.commit()
