# sqlite_store.py
"""Client module for sqlite data store."""

from __future__ import annotations

import contextlib
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any, TypeVar

from riskapp_client.adapters.local_storage.sqlite_schema_definition import ensure_schema
from riskapp_client.adapters.mappers.action_assessment_mapper import (
    action_from_mapping,
    assessment_from_mapping,
)
from riskapp_client.adapters.mappers.scored_entity_mapper import (
    scored_entity_from_mapping,
)
from riskapp_client.domain.domain_models import (
    Action,
    Assessment,
    Opportunity,
    Project,
    Risk,
)
from riskapp_client.domain.scored_entity_fields import (
    SCORED_ENTITY_DB_COLUMNS,
    SCORED_ENTITY_META_KEYS,
    SCORED_ENTITY_META_SQLITE_COLUMNS,
)

ModelT = TypeVar("ModelT")

_TEXT_META_KEYS: set[str] = {
    name
    for name, col_type in SCORED_ENTITY_META_SQLITE_COLUMNS
    if str(col_type).upper().startswith("TEXT")
}
_INT_META_KEYS: set[str] = {
    name
    for name, col_type in SCORED_ENTITY_META_SQLITE_COLUMNS
    if str(col_type).upper().startswith("INTEGER")
}

_VALID_SCORED_TABLES: set[str] = {"risks", "opportunities"}


def utc_iso() -> str:
    """UTC timestamp in ISO-8601 format (naive, server/client must agree)."""
    return datetime.now(UTC).replace(tzinfo=None).isoformat()


def _norm_text(v: str | None) -> str | None:
    """Normalize optional text fields (strip; empty -> None)."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


class LocalStore:
    """Represent Local Store."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        existed = os.path.exists(db_path)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            with contextlib.suppress(OSError):
                os.chmod(db_dir, 0o700)
        # `timeout` helps avoid transient "database is locked" in WAL mode.
        self.conn = sqlite3.connect(self.db_path, timeout=5.0)
        self.conn.row_factory = sqlite3.Row
        # Best-effort private file permissions if we just created the DB.
        if not existed and os.path.exists(db_path):
            with contextlib.suppress(OSError):
                os.chmod(db_path, 0o600)
        self._init_schema()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        with contextlib.suppress(Exception):
            self.conn.close()

    def __enter__(self) -> LocalStore:
        """Return self for context-manager use."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Release resources when leaving the context manager."""
        self.close()

    def _init_schema(self) -> None:
        ensure_schema(self.conn)

    def _upsert_row(
        self, table: str, record: dict[str, Any], cur: Any = None, pk: str = "id"
    ) -> None:
        """Generic upsert that eliminates duplicate SQL strings."""
        cols = list(record.keys())
        placeholders = ", ".join(["?"] * len(cols))
        set_clause = ", ".join([f"{c}=excluded.{c}" for c in cols if c != pk])
        if set_clause:
            sql = (
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT({pk}) DO UPDATE SET {set_clause}"
            )
        else:
            sql = (
                f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT({pk}) DO NOTHING"
            )
        (cur or self.conn).execute(sql, tuple(record[c] for c in cols))

    def get_project(self, project_id: str) -> Project | None:
        """Return project."""
        row = self.conn.execute(
            "SELECT id, name, description FROM projects WHERE id=?;", (project_id,)
        ).fetchone()
        if not row:
            return None
        return Project(
            id=str(row["id"]),
            name=str(row["name"]),
            description=str(row["description"] or ""),
        )

    def create_local_project(
        self,
        *,
        name: str,
        description: str = "",
        project_id: str | None = None,
    ) -> Project:
        """Create a project locally (offline-first bootstrap).

        Local-only projects use a stable prefix so SyncService can detect them
        and create the corresponding server-side project on first sync.
        """
        pid = str(project_id or f"local-{uuid.uuid4()}")
        self._upsert_row(
            "projects",
            {
                "id": pid,
                "name": str(name or "Local Project"),
                "description": description or "",
            },
        )
        self.conn.commit()
        return Project(
            id=pid, name=str(name or "Local Project"), description=description or ""
        )

    def migrate_project_id(self, *, old_project_id: str, new_project_id: str) -> None:
        """Replace a local-only project id with the server project id.

        SQLite does not use ON UPDATE CASCADE for our FKs, so we rebuild the
        relationships by updating all project_id references.

        This is designed for the first online sync of an offline-created project.
        """
        old_id = str(old_project_id)
        new_id = str(new_project_id)
        if not old_id or not new_id or old_id == new_id:
            return
        p = self.get_project(old_id)
        if not p:
            return
        cur = self.conn.cursor()
        cur.execute("PRAGMA foreign_keys=OFF;")
        self._upsert_row(
            "projects",
            {"id": new_id, "name": p.name, "description": p.description or ""},
            cur,
        )
        for table in (
            "risks",
            "opportunities",
            "actions",
            "assessments",
            "sync_state",
            "outbox",
        ):
            cur.execute(
                f"UPDATE {table} SET project_id=? WHERE project_id=?;",
                (new_id, old_id),
            )
        cur.execute("DELETE FROM projects WHERE id=?;", (old_id,))
        cur.execute("PRAGMA foreign_keys=ON;")
        self.conn.commit()
        if (self.get_meta("bootstrap_project_id") or "") == old_id:
            self.set_meta("bootstrap_project_id", new_id)

    def upsert_projects(self, projects: list[Project]) -> None:
        """Insert or update projects."""
        cur = self.conn.cursor()
        for p in projects:
            self._upsert_row(
                "projects",
                {"id": p.id, "name": p.name, "description": p.description or ""},
                cur,
            )
        self.conn.commit()

    def list_actions(self, project_id: str) -> list[Action]:
        """Return actions."""
        rows = self.conn.execute(
            """
            SELECT *
            FROM actions
            WHERE project_id=? AND is_deleted=0
            ORDER BY updated_at DESC, title ASC
            """,
            (project_id,),
        ).fetchall()
        return [action_from_mapping(r) for r in rows]

    def _pending_outbox_ids(self, project_id: str, *, entity: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT entity_id FROM outbox WHERE project_id=? AND entity=? AND status='pending';",
            (project_id, entity),
        ).fetchall()
        return {str(r["entity_id"]) for r in rows}

    def _get_action_row(self, action_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM actions WHERE id=?;", (action_id,)
        ).fetchone()

    def get_action_project_and_version(self, action_id: str) -> tuple[str, int]:
        """Return action project and version."""
        r = self._get_action_row(action_id)
        if not r:
            raise KeyError("action not found in local store")
        return str(r["project_id"]), int(r["version"])

    def upsert_local_action(
        self,
        *,
        action_id: str,
        project_id: str,
        risk_id: str | None,
        opportunity_id: str | None,
        kind: str,
        title: str,
        description: str,
        status: str,
        owner_user_id: str | None,
        version: int | None = None,
        is_deleted: bool | None = None,
        updated_at: str | None = None,
        dirty: int = 1,
    ) -> None:
        """Insert or update local action."""
        existing = self._get_action_row(action_id)

        def _fallback(val, key, default):
            return val if val is not None else (existing[key] if existing else default)

        self._upsert_row(
            "actions",
            {
                "id": action_id,
                "project_id": project_id,
                "risk_id": risk_id,
                "opportunity_id": opportunity_id,
                "kind": kind,
                "title": title,
                "description": description or "",
                "status": status or "open",
                "owner_user_id": owner_user_id,
                "version": int(_fallback(version, "version", 0)),
                "is_deleted": int(_fallback(is_deleted, "is_deleted", 0)),
                "updated_at": str(_fallback(updated_at, "updated_at", "")),
                "dirty": int(dirty),
            },
        )
        self.conn.commit()

    def apply_pull_actions(
        self, project_id: str, server_actions: list[dict[str, Any]]
    ) -> None:
        """Apply pull actions."""
        pending_ids = self._pending_outbox_ids(project_id, entity="action")
        cur = self.conn.cursor()
        for raw in server_actions:
            payload = dict(raw)
            payload.setdefault("project_id", project_id)
            action = action_from_mapping(payload)
            if action.id in pending_ids:
                cur.execute(
                    "UPDATE actions SET version=?, updated_at=? WHERE id=?;",
                    (int(action.version), str(action.updated_at or ""), str(action.id)),
                )
                continue
            record = {
                "id": str(action.id),
                "project_id": project_id,
                "risk_id": action.risk_id,
                "opportunity_id": action.opportunity_id,
                "kind": str(action.kind or ""),
                "title": str(action.title or ""),
                "description": str(action.description or ""),
                "status": str(action.status or "open"),
                "owner_user_id": action.owner_user_id,
                "version": int(action.version),
                "is_deleted": 1 if bool(action.is_deleted) else 0,
                "updated_at": str(action.updated_at or ""),
                "dirty": 0,
            }
            self._upsert_row("actions", record, cur)
        self.conn.commit()

    def list_projects(self) -> list[Project]:
        """Return projects."""
        rows = self.conn.execute(
            "SELECT id, name, description FROM projects ORDER BY name;"
        ).fetchall()
        return [
            Project(id=r["id"], name=r["name"], description=r["description"])
            for r in rows
        ]

    def get_meta(self, key: str) -> str | None:
        """Return meta."""
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key=?;", (key,)
        ).fetchone()
        return str(row["value"]) if row else None

    def set_meta(self, key: str, value: str) -> None:
        """Set meta."""
        self._upsert_row("meta", {"key": key, "value": value}, pk="key")
        self.conn.commit()

    def _next_code(self, project_id: str, *, table: str, prefix: str) -> str:
        """Best-effort local code generator (e.g. R-001 / O-001).

        This satisfies the "Označení" identifier requirement even in offline mode.
        The server remains the source of truth.
        """
        like = f"{prefix}-%"
        rows = self.conn.execute(
            f"SELECT code FROM {table} WHERE project_id=? AND code LIKE ? AND code IS NOT NULL;",
            (project_id, like),
        ).fetchall()
        max_n = 0
        for r in rows:
            c = _norm_text(r["code"])
            if not c:
                continue
            parts = c.split("-", 2)
            if len(parts) < 2:
                continue
            if parts[0].strip().upper() != prefix.upper():
                continue
            num_part = parts[1].strip()
            if num_part.isdigit():
                max_n = max(max_n, int(num_part))
        return f"{prefix}-{max_n + 1:03d}"

    def next_risk_code(self, project_id: str) -> str:
        """Return the next risk code."""
        return self._next_code(project_id, table="risks", prefix="R")

    def next_opportunity_code(self, project_id: str) -> str:
        """Return the next opportunity code."""
        return self._next_code(project_id, table="opportunities", prefix="O")

    def _assert_scored_table(self, table: str) -> None:
        """Internal helper for assert scored table."""
        if table not in _VALID_SCORED_TABLES:
            raise ValueError(f"Invalid scored-entity table: {table!r}")

    def _list_scored_entities(
        self, project_id: str, *, table: str, model_cls: type[ModelT]
    ) -> list[ModelT]:
        """Internal helper for list scored entities."""
        self._assert_scored_table(table)
        cols = ", ".join(SCORED_ENTITY_DB_COLUMNS)
        rows = self.conn.execute(
            f"""
            SELECT {cols}
            FROM {table}
            WHERE project_id=? AND is_deleted=0
            ORDER BY (probability*impact) DESC, title ASC
            """,
            (project_id,),
        ).fetchall()
        return [scored_entity_from_mapping(r, model_cls=model_cls) for r in rows]

    def _get_scored_row(self, table: str, entity_id: str) -> sqlite3.Row | None:
        self._assert_scored_table(table)
        return self.conn.execute(
            f"SELECT * FROM {table} WHERE id=?;", (entity_id,)
        ).fetchone()

    def _get_scored_project_and_version(
        self, table: str, entity_id: str, *, label: str
    ) -> tuple[str, int]:
        row = self._get_scored_row(table, entity_id)
        if not row:
            raise KeyError(f"{label} not found in local store")
        return str(row["project_id"]), int(row["version"])

    def _soft_delete_scored(
        self, table: str, entity_id: str, *, label: str
    ) -> tuple[str, int]:
        self._assert_scored_table(table)
        row = self._get_scored_row(table, entity_id)
        if not row:
            raise KeyError(f"{label} not found in local store")
        project_id = str(row["project_id"])
        version = int(row["version"] or 0)
        self.conn.execute(
            f"UPDATE {table} SET is_deleted=1, dirty=1, updated_at=? WHERE id=?;",
            (utc_iso(), entity_id),
        )
        self.conn.commit()
        return project_id, version

    def _norm_scored_meta(self, meta: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k in SCORED_ENTITY_META_KEYS:
            v = meta.get(k)
            if k in _TEXT_META_KEYS:
                out[k] = _norm_text(v) if v is not None else None
            elif k in _INT_META_KEYS:
                out[k] = int(v) if v is not None else None
            else:
                out[k] = v
        return out

    def _upsert_local_scored(
        self,
        *,
        table: str,
        entity_id: str,
        project_id: str,
        title: str,
        probability: int,
        impact: int,
        meta: dict[str, Any],
        version: int | None,
        is_deleted: bool | None,
        updated_at: str | None,
        dirty: int,
    ) -> None:
        self._assert_scored_table(table)
        existing = self._get_scored_row(table, entity_id)

        def _fallback(val, key, default):
            return val if val is not None else (existing[key] if existing else default)

        v = int(_fallback(version, "version", 0))
        is_del = int(_fallback(is_deleted, "is_deleted", 0))
        upd = str(_fallback(updated_at, "updated_at", ""))
        m = self._norm_scored_meta(meta)
        if not m.get("status"):
            m["status"] = "concept"
        dims = [
            m.get("impact_cost"),
            m.get("impact_time"),
            m.get("impact_scope"),
            m.get("impact_quality"),
        ]
        valid_dims = [int(x) for x in dims if x is not None]
        if valid_dims:
            impact = max(valid_dims)
        record: dict[str, Any] = {
            "id": entity_id,
            "project_id": project_id,
            "title": str(title or ""),
            "probability": int(probability),
            "impact": int(impact),
            **m,
            "version": v,
            "is_deleted": is_del,
            "updated_at": upd,
            "dirty": int(dirty),
        }
        self._upsert_row(table, record)
        self.conn.commit()

    def _apply_pull_scored_entities(
        self,
        project_id: str,
        server_entities: list[dict[str, Any]],
        *,
        table: str,
        outbox_entity: str,
    ) -> None:
        self._assert_scored_table(table)
        pending_ids = {
            r["entity_id"]
            for r in self.conn.execute(
                "SELECT entity_id FROM outbox WHERE project_id=? AND entity=? AND status='pending';",
                (project_id, outbox_entity),
            ).fetchall()
        }
        cur = self.conn.cursor()
        for ent in server_entities:
            eid = str(ent["id"])
            ver = int(ent.get("version") or 0)
            upd = str(ent.get("updated_at") or "")
            if eid in pending_ids:
                cur.execute(
                    f"UPDATE {table} SET version=?, updated_at=? WHERE id=?;",
                    (ver, upd, eid),
                )
                continue
            meta = {k: ent.get(k) for k in SCORED_ENTITY_META_KEYS}
            if not meta.get("status"):
                meta["status"] = "concept"
            m = self._norm_scored_meta(meta)
            record: dict[str, Any] = {
                "id": eid,
                "project_id": project_id,
                "title": str(ent.get("title") or ""),
                "probability": int(ent.get("probability") or 1),
                "impact": int(ent.get("impact") or 1),
                **m,
                "version": ver,
                "is_deleted": 1 if bool(ent.get("is_deleted")) else 0,
                "updated_at": upd,
                "dirty": 0,
            }
            self._upsert_row(table, record, cur)
        self.conn.commit()

    def list_risks(self, project_id: str) -> list[Risk]:
        """Return risks."""
        return self._list_scored_entities(project_id, table="risks", model_cls=Risk)

    def get_risk_row(self, risk_id: str) -> sqlite3.Row | None:
        """Return risk row."""
        return self._get_scored_row("risks", risk_id)

    def get_risk_project_and_version(self, risk_id: str) -> tuple[str, int]:
        """Return risk project and version."""
        return self._get_scored_project_and_version("risks", risk_id, label="risk")

    def upsert_local_risk(
        self,
        *,
        risk_id: str,
        project_id: str,
        title: str,
        probability: int,
        impact: int,
        version: int | None = None,
        is_deleted: bool | None = None,
        updated_at: str | None = None,
        dirty: int = 1,
        **meta: Any,
    ) -> None:
        """Insert or update local risk."""
        self._upsert_local_scored(
            table="risks",
            entity_id=risk_id,
            project_id=project_id,
            title=title,
            probability=probability,
            impact=impact,
            meta=meta,
            version=version,
            is_deleted=is_deleted,
            updated_at=updated_at,
            dirty=dirty,
        )

    def soft_delete_risk(self, risk_id: str) -> tuple[str, int]:
        """Perform soft delete risk."""
        return self._soft_delete_scored("risks", risk_id, label="risk")

    def _mark_entity_clean(self, table: str, entity_id: str) -> None:
        self.conn.execute(f"UPDATE {table} SET dirty=0 WHERE id=?;", (entity_id,))
        self.conn.commit()

    def mark_risk_clean(self, risk_id: str) -> None:
        """Mark risk clean."""
        self._mark_entity_clean("risks", risk_id)

    def mark_opportunity_clean(self, opportunity_id: str) -> None:
        """Mark opportunity clean."""
        self._mark_entity_clean("opportunities", opportunity_id)

    def mark_action_clean(self, action_id: str) -> None:
        """Mark action clean."""
        self._mark_entity_clean("actions", action_id)

    def mark_assessment_clean(self, assessment_id: str) -> None:
        """Mark assessment clean."""
        self._mark_entity_clean("assessments", assessment_id)

    def list_opportunities(self, project_id: str) -> list[Opportunity]:
        """Return opportunities."""
        return self._list_scored_entities(
            project_id, table="opportunities", model_cls=Opportunity
        )

    def get_opportunity_row(self, opportunity_id: str) -> sqlite3.Row | None:
        """Return opportunity row."""
        return self._get_scored_row("opportunities", opportunity_id)

    def get_opportunity_project_and_version(
        self, opportunity_id: str
    ) -> tuple[str, int]:
        """Return opportunity project and version."""
        return self._get_scored_project_and_version(
            "opportunities", opportunity_id, label="opportunity"
        )

    def upsert_local_opportunity(
        self,
        *,
        opportunity_id: str,
        project_id: str,
        title: str,
        probability: int,
        impact: int,
        version: int | None = None,
        is_deleted: bool | None = None,
        updated_at: str | None = None,
        dirty: int = 1,
        **meta: Any,
    ) -> None:
        """Insert or update local opportunity."""
        self._upsert_local_scored(
            table="opportunities",
            entity_id=opportunity_id,
            project_id=project_id,
            title=title,
            probability=probability,
            impact=impact,
            meta=meta,
            version=version,
            is_deleted=is_deleted,
            updated_at=updated_at,
            dirty=dirty,
        )

    def soft_delete_opportunity(self, opportunity_id: str) -> tuple[str, int]:
        """Perform soft delete opportunity."""
        return self._soft_delete_scored(
            "opportunities", opportunity_id, label="opportunity"
        )

    def list_assessments(
        self, project_id: str, item_type: str, item_id: str
    ) -> list[Assessment]:
        """Return assessments."""
        rows = self.conn.execute(
            """
            SELECT * FROM assessments
            WHERE project_id=? AND is_deleted=0 AND item_type=?
                AND (item_id=? OR risk_id=? OR opportunity_id=?)
            ORDER BY updated_at DESC
            """,
            (project_id, item_type, item_id, item_id, item_id),
        ).fetchall()
        return [assessment_from_mapping(r) for r in rows]

    def get_assessment_project_and_version(self, assessment_id: str) -> tuple[str, int]:
        """Return assessment project and version."""
        row = self.conn.execute(
            "SELECT project_id, version FROM assessments WHERE id=?;",
            (assessment_id,),
        ).fetchone()
        if not row:
            raise ValueError("assessment not found")
        return (str(row["project_id"]), int(row["version"]))

    def upsert_local_assessment(
        self,
        *,
        assessment_id: str,
        project_id: str,
        item_type: str,
        item_id: str,
        assessor_user_id: str,
        probability: int,
        impact: int,
        notes: str | None,
        version: int,
        is_deleted: bool,
        updated_at: str,
        dirty: int,
    ) -> None:
        """Insert or update local assessment."""
        score = int(probability) * int(impact)
        itype = str(item_type or "risk").strip().lower() or "risk"
        risk_id = item_id if itype == "risk" else None
        opp_id = item_id if itype == "opportunity" else None
        self._upsert_row(
            "assessments",
            {
                "id": assessment_id,
                "project_id": project_id,
                # Backward-compat fields; nullable (no FK).
                "risk_id": risk_id,
                "opportunity_id": opp_id,
                "item_id": item_id,
                "item_type": itype,
                "assessor_user_id": assessor_user_id,
                "probability": int(probability),
                "impact": int(impact),
                "score": score,
                "notes": notes or "",
                "version": int(version),
                "is_deleted": 1 if is_deleted else 0,
                "updated_at": updated_at,
                "dirty": int(dirty),
            },
        )
        self.conn.commit()

    def get_last_server_time(self, project_id: str) -> str:
        """Return last server time."""
        row = self.conn.execute(
            "SELECT last_server_time FROM sync_state WHERE project_id=?;", (project_id,)
        ).fetchone()
        return str(row["last_server_time"]) if row else "1970-01-01T00:00:00"

    def set_last_server_time(self, project_id: str, server_time: str) -> None:
        """Set last server time."""
        self._upsert_row(
            "sync_state",
            {"project_id": project_id, "last_server_time": server_time},
            pk="project_id",
        )
        self.conn.commit()

    def apply_pull_risks(
        self, project_id: str, server_risks: list[dict[str, Any]]
    ) -> None:
        """Apply pull risks."""
        self._apply_pull_scored_entities(
            project_id,
            server_risks,
            table="risks",
            outbox_entity="risk",
        )

    def apply_pull_opportunities(
        self, project_id: str, server_opps: list[dict[str, Any]]
    ) -> None:
        """Apply pull opportunities."""
        self._apply_pull_scored_entities(
            project_id,
            server_opps,
            table="opportunities",
            outbox_entity="opportunity",
        )

    def apply_pull_assessments(
        self, project_id: str, server_assessments: list[dict[str, Any]]
    ) -> None:
        """Apply pull assessments."""
        pending_ids = self._pending_outbox_ids(project_id, entity="assessment")
        cur = self.conn.cursor()
        for raw in server_assessments:
            assessment = assessment_from_mapping(raw)
            score = int(assessment.score)
            is_del = 1 if bool(assessment.is_deleted) else 0
            upd = str(assessment.updated_at or "")
            ver = int(assessment.version)
            if assessment.id in pending_ids:
                cur.execute(
                    "UPDATE assessments SET version=?, updated_at=? WHERE id=?;",
                    (ver, upd, str(assessment.id)),
                )
                continue
            item_type = (
                "risk"
                if raw.get("risk_id")
                else ("opportunity" if raw.get("opportunity_id") else "risk")
            )
            risk_id = str(assessment.item_id) if item_type == "risk" else None
            opp_id = str(assessment.item_id) if item_type == "opportunity" else None
            record = {
                "id": str(assessment.id),
                "project_id": project_id,
                "risk_id": risk_id,
                "opportunity_id": opp_id,
                "item_id": str(assessment.item_id),
                "item_type": str(item_type),
                "assessor_user_id": str(assessment.assessor_user_id or ""),
                "probability": int(assessment.probability),
                "impact": int(assessment.impact),
                "score": score,
                "notes": str(assessment.notes or ""),
                "version": ver,
                "is_deleted": is_del,
                "updated_at": upd,
                "dirty": 0,
            }
            self._upsert_row("assessments", record, cur)
        self.conn.commit()
