"""SQLite schema management.

Goals:
- Keep DDL/migrations readable and deterministic.
- Avoid try/except-driven migrations when we can cheaply introspect.
- Be safe to call repeatedly (idempotent).

This module is intentionally dependency-light and does not import LocalStore.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable, Sequence

from riskapp_client.domain.scored_entity_fields import SCORED_ENTITY_META_SQLITE_COLUMNS


def _exec(conn: sqlite3.Connection, sql: str) -> None:
    conn.execute(sql)


def _exec_many(conn: sqlite3.Connection, ddls: Iterable[str]) -> None:
    for ddl in ddls:
        _exec(conn, ddl)


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    # PRAGMA table_info returns rows: (cid, name, type, notnull, dflt_value, pk)
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return {str(r[1]) for r in rows}


def ensure_columns(conn: sqlite3.Connection, table: str, columns: Sequence[tuple[str, str]]) -> None:
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
                risk_id TEXT NOT NULL,
                assessor_user_id TEXT NOT NULL DEFAULT '',
                probability INTEGER NOT NULL,
                impact INTEGER NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                version INTEGER NOT NULL DEFAULT 0,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT '',
                dirty INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(risk_id) REFERENCES risks(id)
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

    # ---- Schema upgrades (idempotent, based on introspection) ----

    # Scored-entity assignment/meta fields
    ensure_columns(conn, "risks", SCORED_ENTITY_META_SQLITE_COLUMNS)
    ensure_columns(conn, "opportunities", SCORED_ENTITY_META_SQLITE_COLUMNS)

    # Assessment score (older DBs may not have it)
    ensure_columns(conn, "assessments", [("score", "INTEGER NOT NULL DEFAULT 0")])

    # ---- Indexes ----

    _exec_many(
        conn,
        [
            "CREATE INDEX IF NOT EXISTS risks_project_idx ON risks(project_id, is_deleted, updated_at);",
            "CREATE INDEX IF NOT EXISTS opps_project_idx ON opportunities(project_id, is_deleted, updated_at);",
            "CREATE INDEX IF NOT EXISTS actions_project_idx ON actions(project_id, is_deleted, updated_at);",
            "CREATE INDEX IF NOT EXISTS outbox_pending_idx ON outbox(project_id, status, created_at);",
            "CREATE INDEX IF NOT EXISTS outbox_entity_idx ON outbox(project_id, entity, entity_id);",
            "CREATE INDEX IF NOT EXISTS assessments_risk_idx ON assessments(project_id, risk_id, is_deleted);",
            "CREATE INDEX IF NOT EXISTS assessments_user_idx ON assessments(project_id, assessor_user_id);",
            # Code should be unique within a project (NULLs allowed).
            # Create after columns exist.
            "CREATE UNIQUE INDEX IF NOT EXISTS risks_project_code_uq ON risks(project_id, code);",
            "CREATE UNIQUE INDEX IF NOT EXISTS opps_project_code_uq ON opportunities(project_id, code);",
        ],
    )

    conn.commit()
