"""Test module for test sqlite schema migration."""

from __future__ import annotations

import sqlite3


def _create_legacy_db(path: str) -> None:
    """Internal helper for create legacy db."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")

    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE risks (
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

        -- legacy broken table: FK to risks and NOT NULL risk_id
        CREATE TABLE assessments (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            risk_id TEXT NOT NULL,
            assessor_user_id TEXT NOT NULL,
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
        """
    )

    conn.execute("INSERT INTO projects (id, name, description) VALUES ('p1', 'P', '');")
    conn.execute(
        "INSERT INTO risks (id, project_id, title, probability, impact) VALUES ('r1','p1','R',2,2);"
    )
    conn.execute(
        "INSERT INTO assessments (id, project_id, risk_id, assessor_user_id, probability, impact, score) "
        "VALUES ('a1','p1','r1','u1',3,4,12);"
    )
    conn.commit()
    conn.close()


def test_assessment_fk_migration_removes_risks_fk_and_adds_opportunity_id(
    tmp_path,
) -> None:
    """Test that assessment fk migration removes risks fk and adds opportunity id."""
    db_file = tmp_path / "legacy.db"
    _create_legacy_db(str(db_file))

    # Opening LocalStore triggers ensure_schema() and runs the migration.
    from riskapp_client.adapters.local_storage.sqlite_data_store import LocalStore

    store = LocalStore(str(db_file))
    try:
        cols = store.conn.execute("PRAGMA table_info(assessments);").fetchall()
        col_names = {str(c[1]) for c in cols}

        assert "opportunity_id" in col_names
        assert "risk_id" in col_names
        assert "item_id" in col_names
        assert "item_type" in col_names

        # FK to risks must be gone.
        fks = store.conn.execute("PRAGMA foreign_key_list(assessments);").fetchall()
        assert all(str(r[2]) != "risks" for r in fks)

        # Existing data should still be present and canonicalized.
        row = store.conn.execute(
            "SELECT id, risk_id, opportunity_id, item_id, item_type FROM assessments WHERE id='a1';"
        ).fetchone()
        assert row is not None
        assert row["item_type"] == "risk"
        assert row["item_id"] == "r1"
        assert row["risk_id"] == "r1"
        assert row["opportunity_id"] is None
    finally:
        store.close()
