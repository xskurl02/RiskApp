# sqlite_store.py
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from riskapp_client.domain.models import Project, Risk, Opportunity, Action, Assessment
from riskapp_client.domain.scored_fields import SCORED_ENTITY_META_SQLITE_COLUMNS

def utc_iso() -> str:
    return datetime.utcnow().isoformat()

class LocalStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

        existed = os.path.exists(db_path)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            # Best-effort private directory (POSIX). On Windows this is a no-op.
            os.makedirs(db_dir, exist_ok=True)
            try:
                os.chmod(db_dir, 0o700)
            except OSError:
                pass

        # `timeout` helps avoid transient "database is locked" in WAL mode.
        self.conn = sqlite3.connect(self.db_path, timeout=5.0)
        self.conn.row_factory = sqlite3.Row

        # Best-effort private file permissions if we just created the DB.
        if not existed and os.path.exists(db_path):
            try:
                os.chmod(db_path, 0o600)
            except OSError:
                pass

        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA foreign_keys=ON;")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT ''
            );
            """
        )

        cur.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        cur.execute(
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
            """
        )

        try:
            cur.execute("ALTER TABLE assessments ADD COLUMN score INTEGER NOT NULL DEFAULT 0;")
        except sqlite3.OperationalError:
            pass


        cur.execute(
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
            """
        )

        cur.execute(
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
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS risks_project_idx ON risks(project_id, is_deleted, updated_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS opps_project_idx ON opportunities(project_id, is_deleted, updated_at);")

        # offline_backend.py inside LocalStore._init_schema, after CREATE TABLE risks/opportunities

        # --- schema upgrades for assignment fields (safe to run repeatedly) ---
        for sql in (
            [f"ALTER TABLE risks ADD COLUMN {name} {typ};" for name, typ in SCORED_ENTITY_META_SQLITE_COLUMNS]
            + [f"ALTER TABLE opportunities ADD COLUMN {name} {typ};" for name, typ in SCORED_ENTITY_META_SQLITE_COLUMNS]
        ):
            try:
                cur.execute(sql)
            except sqlite3.OperationalError:
                pass

        # --- indexes / constraints ---
        # Code should be unique within a project (NULLs allowed).
        # IMPORTANT: create after tables exist AND after the `code` columns are added.
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS risks_project_code_uq ON risks(project_id, code);")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS opps_project_code_uq ON opportunities(project_id, code);")
        except sqlite3.OperationalError:
            pass

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                project_id TEXT PRIMARY KEY,
                last_server_time TEXT NOT NULL
            );
            """
        )

        cur.execute(
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
            """
        )
        cur.execute(
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
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS actions_project_idx ON actions(project_id, is_deleted, updated_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS outbox_pending_idx ON outbox(project_id, status, created_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS outbox_entity_idx ON outbox(project_id, entity, entity_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS assessments_risk_idx ON assessments(project_id, risk_id, is_deleted);")
        cur.execute("CREATE INDEX IF NOT EXISTS assessments_user_idx ON assessments(project_id, assessor_user_id);")
        self.conn.commit()

    # --------- Projects ---------

    def upsert_projects(self, projects: List[Project]) -> None:
        cur = self.conn.cursor()
        for p in projects:
            cur.execute(
                """
                INSERT INTO projects (id, name, description)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name,
                  description=excluded.description
                """,
                (p.id, p.name, p.description or ""),
            )
        self.conn.commit()

    def list_actions(self, project_id: str) -> List[Action]:
        rows = self.conn.execute(
            """
            SELECT *
            FROM actions
            WHERE project_id=? AND is_deleted=0
            ORDER BY updated_at DESC, title ASC
            """,
            (project_id,),
        ).fetchall()

        return [
            Action(
                id=r["id"],
                project_id=r["project_id"],
                risk_id=r["risk_id"],
                opportunity_id=r["opportunity_id"],
                kind=r["kind"],
                title=r["title"],
                description=r["description"] or "",
                status=r["status"] or "open",
                owner_user_id=r["owner_user_id"],
                version=int(r["version"]),
                is_deleted=bool(r["is_deleted"]),
                updated_at=r["updated_at"] or "",
            )
            for r in rows
        ]

    def _get_action_row(self, action_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM actions WHERE id=?;", (action_id,)).fetchone()

    def get_action_project_and_version(self, action_id: str) -> Tuple[str, int]:
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
        version: Optional[int] = None,
        is_deleted: Optional[bool] = None,
        updated_at: Optional[str] = None,
        dirty: int = 1,
    ) -> None:
        existing = self._get_action_row(action_id)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO actions (
            id, project_id, risk_id, opportunity_id, kind, title, description, status, owner_user_id,
            version, is_deleted, updated_at, dirty
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
            project_id=excluded.project_id,
            risk_id=excluded.risk_id,
            opportunity_id=excluded.opportunity_id,
            kind=excluded.kind,
            title=excluded.title,
            description=excluded.description,
            status=excluded.status,
            owner_user_id=excluded.owner_user_id,
            version=excluded.version,
            is_deleted=excluded.is_deleted,
            updated_at=excluded.updated_at,
            dirty=excluded.dirty
            """,
            (
                action_id,
                project_id,
                risk_id,
                opportunity_id,
                kind,
                title,
                description or "",
                status or "open",
                owner_user_id,
                int(version if version is not None else (existing["version"] if existing else 0)),
                int(is_deleted if is_deleted is not None else (existing["is_deleted"] if existing else 0)),
                str(updated_at if updated_at is not None else (existing["updated_at"] if existing else "")),
                int(dirty),
            ),
        )
        self.conn.commit()

    def apply_pull_actions(self, project_id: str, server_actions: List[Dict[str, Any]]) -> None:
        pending_ids = {
            r["entity_id"]
            for r in self.conn.execute(
                "SELECT entity_id FROM outbox WHERE project_id=? AND entity='action' AND status='pending';",
                (project_id,),
            ).fetchall()
        }

        cur = self.conn.cursor()
        for a in server_actions:
            aid = str(a["id"])
            upd = str(a.get("updated_at") or "")
            ver = int(a.get("version") or 0)
            is_del = 1 if bool(a.get("is_deleted")) else 0

            if aid in pending_ids:
                cur.execute("UPDATE actions SET version=?, updated_at=? WHERE id=?;", (ver, upd, aid))
                continue

            cur.execute(
                """
                INSERT INTO actions (
                id, project_id, risk_id, opportunity_id, kind, title, description, status, owner_user_id,
                version, is_deleted, updated_at, dirty
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(id) DO UPDATE SET
                project_id=excluded.project_id,
                risk_id=excluded.risk_id,
                opportunity_id=excluded.opportunity_id,
                kind=excluded.kind,
                title=excluded.title,
                description=excluded.description,
                status=excluded.status,
                owner_user_id=excluded.owner_user_id,
                version=excluded.version,
                is_deleted=excluded.is_deleted,
                updated_at=excluded.updated_at,
                dirty=0
                """,
                (
                    aid,
                    project_id,
                    str(a.get("risk_id")) if a.get("risk_id") else None,
                    str(a.get("opportunity_id")) if a.get("opportunity_id") else None,
                    str(a.get("kind") or ""),
                    str(a.get("title") or ""),
                    str(a.get("description") or "") if a.get("description") else "",
                    str(a.get("status") or "open"),
                    str(a.get("owner_user_id")) if a.get("owner_user_id") else None,
                    ver,
                    is_del,
                    upd,
                ),
            )

        self.conn.commit()

    def list_projects(self) -> List[Project]:
        rows = self.conn.execute("SELECT id, name, description FROM projects ORDER BY name;").fetchall()
        return [Project(id=r["id"], name=r["name"], description=r["description"]) for r in rows]

    def get_meta(self, key: str) -> Optional[str]:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?;", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta(key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()
    
    # --------- Risks ---------

    def list_risks(self, project_id: str) -> List[Risk]:
        rows = self.conn.execute(
            """
            SELECT
            id, project_id, code, title, description, category, threat, triggers,
            mitigation_plan, document_url,
            owner_user_id, status,
            identified_at, status_changed_at, response_at, occurred_at,
            impact_cost, impact_time, impact_scope, impact_quality,
            probability, impact, version, is_deleted, updated_at
            FROM risks
            WHERE project_id=? AND is_deleted=0
            ORDER BY (probability*impact) DESC, title ASC
            """,
            (project_id,),
        ).fetchall()

        return [
            Risk(
                id=r["id"],
                project_id=r["project_id"],
                code=r["code"],
                title=r["title"],
                description=r["description"],
                category=r["category"],
                threat=r["threat"],
                triggers=r["triggers"],
                mitigation_plan=r["mitigation_plan"],
                document_url=r["document_url"],
                owner_user_id=r["owner_user_id"],
                status=r["status"],
                identified_at=r["identified_at"],
                status_changed_at=r["status_changed_at"],
                response_at=r["response_at"],
                occurred_at=r["occurred_at"],
                probability=int(r["probability"]),
                impact=int(r["impact"]),
                impact_cost=(int(r["impact_cost"]) if r["impact_cost"] is not None else None),
                impact_time=(int(r["impact_time"]) if r["impact_time"] is not None else None),
                impact_scope=(int(r["impact_scope"]) if r["impact_scope"] is not None else None),
                impact_quality=(int(r["impact_quality"]) if r["impact_quality"] is not None else None),
                version=int(r["version"]),
                is_deleted=bool(r["is_deleted"]),
                updated_at=r["updated_at"] or "",
            )
            for r in rows
        ]


    def _get_risk_row(self, risk_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM risks WHERE id=?;", (risk_id,)).fetchone()

    def get_risk_row(self, risk_id: str) -> sqlite3.Row | None:
        return self._get_risk_row(risk_id)

    def get_risk_project_and_version(self, risk_id: str) -> Tuple[str, int]:
        r = self._get_risk_row(risk_id)
        if not r:
            raise KeyError("risk not found in local store")
        return str(r["project_id"]), int(r["version"])

    def upsert_local_risk(
        self,
        *,
        risk_id: str,
        project_id: str,
        title: str,
        probability: int,
        impact: int,
        impact_cost: int | None = None,
        impact_time: int | None = None,
        impact_scope: int | None = None,
        impact_quality: int | None = None,
        code: str | None = None,
        description: str | None = None,
        category: str | None = None,
        threat: str | None = None,
        triggers: str | None = None,
        mitigation_plan: str | None = None,
        document_url: str | None = None,
        owner_user_id: str | None = None,
        status: str | None = None,
        identified_at: str | None = None,
        status_changed_at: str | None = None,
        response_at: str | None = None,
        occurred_at: str | None = None,
        version: Optional[int] = None,
        is_deleted: Optional[bool] = None,
        updated_at: Optional[str] = None,
        dirty: int = 1,
    ) -> None:
        existing = self._get_risk_row(risk_id)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO risks (
            id, project_id, code, title, description, category, threat, triggers,
            mitigation_plan, document_url,
            owner_user_id, status,
            identified_at, status_changed_at, response_at, occurred_at,
            impact_cost, impact_time, impact_scope, impact_quality,
            probability, impact, version, is_deleted, updated_at, dirty
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
            project_id=excluded.project_id,
            code=excluded.code,
            title=excluded.title,
            description=excluded.description,
            category=excluded.category,
            threat=excluded.threat,
            triggers=excluded.triggers,
            mitigation_plan=excluded.mitigation_plan,
            document_url=excluded.document_url,
            owner_user_id=excluded.owner_user_id,
            status=excluded.status,
            identified_at=excluded.identified_at,
            status_changed_at=excluded.status_changed_at,
            response_at=excluded.response_at,
            occurred_at=excluded.occurred_at,
            impact_cost=excluded.impact_cost,
            impact_time=excluded.impact_time,
            impact_scope=excluded.impact_scope,
            impact_quality=excluded.impact_quality,
            probability=excluded.probability,
            impact=excluded.impact,
            version=excluded.version,
            is_deleted=excluded.is_deleted,
            updated_at=excluded.updated_at,
            dirty=excluded.dirty
            """,
            (
                risk_id,
                project_id,
                (code if code is not None else (existing["code"] if existing else None)),
                title,
                (description if description is not None else (existing["description"] if existing else None)),
                (category if category is not None else (existing["category"] if existing else None)),
                (threat if threat is not None else (existing["threat"] if existing else None)),
                (triggers if triggers is not None else (existing["triggers"] if existing else None)),
                (mitigation_plan if mitigation_plan is not None else (existing["mitigation_plan"] if existing else None)),
                (document_url if document_url is not None else (existing["document_url"] if existing else None)),
                (owner_user_id if owner_user_id is not None else (existing["owner_user_id"] if existing else None)),
                (status if status is not None else (existing["status"] if existing else None)),
                (identified_at if identified_at is not None else (existing["identified_at"] if existing else None)),
                (status_changed_at if status_changed_at is not None else (existing["status_changed_at"] if existing else None)),
                (response_at if response_at is not None else (existing["response_at"] if existing else None)),
                (occurred_at if occurred_at is not None else (existing["occurred_at"] if existing else None)),
                (impact_cost if impact_cost is not None else (existing["impact_cost"] if existing else None)),
                (impact_time if impact_time is not None else (existing["impact_time"] if existing else None)),
                (impact_scope if impact_scope is not None else (existing["impact_scope"] if existing else None)),
                (impact_quality if impact_quality is not None else (existing["impact_quality"] if existing else None)),
                int(probability),
                int(impact),
                int(version if version is not None else (existing["version"] if existing else 0)),
                int(is_deleted if is_deleted is not None else (existing["is_deleted"] if existing else 0)),
                str(updated_at if updated_at is not None else (existing["updated_at"] if existing else "")),
                int(dirty),
            ),
        )
        self.conn.commit()

    def mark_risk_clean(self, risk_id: str) -> None:
        self.conn.execute("UPDATE risks SET dirty=0 WHERE id=?;", (risk_id,))
        self.conn.commit()
    
    # --------- Opportunities ---------
    def list_opportunities(self, project_id: str) -> List[Opportunity]:
        rows = self.conn.execute(
            """
            SELECT
            id, project_id, code, title, description, category, threat, triggers,
            mitigation_plan, document_url,
            owner_user_id, status,
            identified_at, status_changed_at, response_at, occurred_at,
            impact_cost, impact_time, impact_scope, impact_quality,
            probability, impact, version, is_deleted, updated_at
            FROM opportunities
            WHERE project_id=? AND is_deleted=0
            ORDER BY (probability*impact) DESC, title ASC
            """,
            (project_id,),
        ).fetchall()

        return [
            Opportunity(
                id=r["id"],
                project_id=r["project_id"],
                code=r["code"],
                title=r["title"],
                description=r["description"],
                category=r["category"],
                threat=r["threat"],
                triggers=r["triggers"],
                mitigation_plan=r["mitigation_plan"],
                document_url=r["document_url"],
                owner_user_id=r["owner_user_id"],
                status=r["status"],
                identified_at=r["identified_at"],
                status_changed_at=r["status_changed_at"],
                response_at=r["response_at"],
                occurred_at=r["occurred_at"],
                probability=int(r["probability"]),
                impact=int(r["impact"]),
                impact_cost=(int(r["impact_cost"]) if r["impact_cost"] is not None else None),
                impact_time=(int(r["impact_time"]) if r["impact_time"] is not None else None),
                impact_scope=(int(r["impact_scope"]) if r["impact_scope"] is not None else None),
                impact_quality=(int(r["impact_quality"]) if r["impact_quality"] is not None else None),
                version=int(r["version"]),
                is_deleted=bool(r["is_deleted"]),
                updated_at=r["updated_at"] or "",
            )
            for r in rows
        ]

    def _get_opportunity_row(self, opportunity_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM opportunities WHERE id=?;", (opportunity_id,)).fetchone()
    
    def get_opportunity_row(self, opportunity_id: str) -> sqlite3.Row | None:
        return self._get_opportunity_row(opportunity_id)

    def get_opportunity_project_and_version(self, opportunity_id: str) -> Tuple[str, int]:
        r = self._get_opportunity_row(opportunity_id)
        if not r:
            raise KeyError("opportunity not found in local store")
        return str(r["project_id"]), int(r["version"])

    def upsert_local_opportunity(
        self,
        *,
        opportunity_id: str,
        project_id: str,
        title: str,
        probability: int,
        impact: int,
        impact_cost: int | None = None,
        impact_time: int | None = None,
        impact_scope: int | None = None,
        impact_quality: int | None = None,
        code: str | None = None,
        description: str | None = None,
        category: str | None = None,
        threat: str | None = None,
        triggers: str | None = None,
        mitigation_plan: str | None = None,
        document_url: str | None = None,
        owner_user_id: str | None = None,
        status: str | None = None,
        identified_at: str | None = None,
        status_changed_at: str | None = None,
        response_at: str | None = None,
        occurred_at: str | None = None,
        version: Optional[int] = None,
        is_deleted: Optional[bool] = None,
        updated_at: Optional[str] = None,
        dirty: int = 1,
    ) -> None:
        def _norm_text(v: str | None) -> str | None:
            if v is None:
                return None
            s = str(v).strip()
            return s if s else None

        existing = self._get_opportunity_row(opportunity_id)
        cur = self.conn.cursor()

        cur.execute(
            """
            INSERT INTO opportunities (
            id, project_id,
            code, title, description, category, threat, triggers,
            mitigation_plan, document_url,
            owner_user_id, status,
            identified_at, status_changed_at, response_at, occurred_at,
            impact_cost, impact_time, impact_scope, impact_quality,
            probability, impact,
            version, is_deleted, updated_at, dirty
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
            project_id=excluded.project_id,
            code=excluded.code,
            title=excluded.title,
            description=excluded.description,
            category=excluded.category,
            threat=excluded.threat,
            triggers=excluded.triggers,
            mitigation_plan=excluded.mitigation_plan,
            document_url=excluded.document_url,
            owner_user_id=excluded.owner_user_id,
            status=excluded.status,
            identified_at=excluded.identified_at,
            status_changed_at=excluded.status_changed_at,
            response_at=excluded.response_at,
            occurred_at=excluded.occurred_at,
            impact_cost=excluded.impact_cost,
            impact_time=excluded.impact_time,
            impact_scope=excluded.impact_scope,
            impact_quality=excluded.impact_quality,
            probability=excluded.probability,
            impact=excluded.impact,
            version=excluded.version,
            is_deleted=excluded.is_deleted,
            updated_at=excluded.updated_at,
            dirty=excluded.dirty
            """,
            (
                opportunity_id,
                project_id,

                # metadata (keep existing value if arg is None)
                (_norm_text(code) if code is not None else (existing["code"] if existing else None)),
                title,
                (description if description is not None else (existing["description"] if existing else None)),
                (_norm_text(category) if category is not None else (existing["category"] if existing else None)),
                (threat if threat is not None else (existing["threat"] if existing else None)),
                (triggers if triggers is not None else (existing["triggers"] if existing else None)),
                (mitigation_plan if mitigation_plan is not None else (existing["mitigation_plan"] if existing else None)),
                (document_url if document_url is not None else (existing["document_url"] if existing else None)),
                (_norm_text(owner_user_id) if owner_user_id is not None else (existing["owner_user_id"] if existing else None)),
                (_norm_text(status) if status is not None else (existing["status"] if existing else None)),
                (_norm_text(identified_at) if identified_at is not None else (existing["identified_at"] if existing else None)),
                (_norm_text(status_changed_at) if status_changed_at is not None else (existing["status_changed_at"] if existing else None)),
                (_norm_text(response_at) if response_at is not None else (existing["response_at"] if existing else None)),
                (_norm_text(occurred_at) if occurred_at is not None else (existing["occurred_at"] if existing else None)),
                (impact_cost if impact_cost is not None else (existing["impact_cost"] if existing else None)),
                (impact_time if impact_time is not None else (existing["impact_time"] if existing else None)),
                (impact_scope if impact_scope is not None else (existing["impact_scope"] if existing else None)),
                (impact_quality if impact_quality is not None else (existing["impact_quality"] if existing else None)),

                int(probability),
                int(impact),

                int(version if version is not None else (existing["version"] if existing else 0)),
                int(is_deleted if is_deleted is not None else (existing["is_deleted"] if existing else 0)),
                str(updated_at if updated_at is not None else (existing["updated_at"] if existing else "")),
                int(dirty),
            ),
        )
        self.conn.commit()


    def list_assessments(self, project_id: str, risk_id: str) -> List[Assessment]:
        rows = self.conn.execute(
            """
            SELECT * FROM assessments
            WHERE project_id=? AND risk_id=? AND is_deleted=0
            ORDER BY updated_at DESC
            """,
            (project_id, risk_id),
        ).fetchall()

        out: List[Assessment] = []
        for r in rows:
            out.append(Assessment(
                id=r["id"],
                risk_id=r["risk_id"],
                assessor_user_id=r["assessor_user_id"],
                probability=int(r["probability"]),
                impact=int(r["impact"]),
                score=int(r["score"]),
                notes=r["notes"],
                updated_at=r["updated_at"],
                version=int(r["version"]),
                is_deleted=bool(r["is_deleted"]),
            ))
        return out

    def get_assessment_project_and_version(self, assessment_id: str) -> Tuple[str, int]:
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
        risk_id: str,
        assessor_user_id: str,
        probability: int,
        impact: int,
        notes: Optional[str],
        version: int,
        is_deleted: bool,
        updated_at: str,
        dirty: int,
    ) -> None:
        score = int(probability) * int(impact)
        self.conn.execute(
            """
            INSERT INTO assessments (id, project_id, risk_id, assessor_user_id, probability, impact, score, notes,
                                    version, is_deleted, updated_at, dirty)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
            project_id=excluded.project_id,
            risk_id=excluded.risk_id,
            assessor_user_id=excluded.assessor_user_id,
            probability=excluded.probability,
            impact=excluded.impact,
            score=excluded.score,
            notes=excluded.notes,
            version=excluded.version,
            is_deleted=excluded.is_deleted,
            updated_at=excluded.updated_at,
            dirty=excluded.dirty
            """,
            (assessment_id, project_id, risk_id, assessor_user_id, int(probability), int(impact), score, notes,
            int(version), 1 if is_deleted else 0, updated_at, int(dirty)),
        )
        self.conn.commit()

    # --------- Sync state ---------

    def get_last_server_time(self, project_id: str) -> str:
        row = self.conn.execute("SELECT last_server_time FROM sync_state WHERE project_id=?;", (project_id,)).fetchone()
        return str(row["last_server_time"]) if row else "1970-01-01T00:00:00"

    def set_last_server_time(self, project_id: str, server_time: str) -> None:
        self.conn.execute(
            """
            INSERT INTO sync_state(project_id, last_server_time)
            VALUES (?, ?)
            ON CONFLICT(project_id) DO UPDATE SET last_server_time=excluded.last_server_time
            """,
            (project_id, server_time),
        )
        self.conn.commit()

    # --------- Apply pull ---------

    def apply_pull_risks(self, project_id: str, server_risks: List[Dict[str, Any]]) -> None:
        # Don’t overwrite local content for risks that still have pending outbox changes.
        pending_ids = {
            r["entity_id"]
            for r in self.conn.execute(
                "SELECT entity_id FROM outbox WHERE project_id=? AND entity='risk' AND status='pending';",
                (project_id,),
            ).fetchall()
        }

        cur = self.conn.cursor()
        for r in server_risks:
            rid = str(r["id"])

            # core
            title = str(r.get("title") or "")
            p = int(r.get("probability") or 1)
            i = int(r.get("impact") or 1)

            # metadata
            code = r.get("code")
            description = r.get("description")
            category = r.get("category")
            threat = r.get("threat")
            triggers = r.get("triggers")
            owner_user_id = r.get("owner_user_id")
            status = str(r.get("status") or "concept")

            identified_at = r.get("identified_at")
            status_changed_at = r.get("status_changed_at")
            response_at = r.get("response_at")
            occurred_at = r.get("occurred_at")
            mitigation_plan = r.get("mitigation_plan")
            document_url = r.get("document_url")
            impact_cost = r.get("impact_cost")
            impact_time = r.get("impact_time")
            impact_scope = r.get("impact_scope")
            impact_quality = r.get("impact_quality")
            # sync meta
            ver = int(r.get("version") or 0)
            is_del = 1 if bool(r.get("is_deleted")) else 0
            upd = str(r.get("updated_at") or "")

            if rid in pending_ids:
                # keep local fields, only update version/updated_at
                cur.execute("UPDATE risks SET version=?, updated_at=? WHERE id=?", (ver, upd, rid))
            else:
                cur.execute(
                    """
                    INSERT INTO risks (
                        id, project_id,
                        title, probability, impact,
                        code, description, category, threat, triggers,
                        owner_user_id, status,
                        identified_at, status_changed_at, response_at, occurred_at,
                        mitigation_plan, document_url,
                        impact_cost, impact_time, impact_scope, impact_quality,
                        version, is_deleted, updated_at, dirty
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    title=excluded.title,
                    probability=excluded.probability,
                    impact=excluded.impact,
                    code=excluded.code,
                    description=excluded.description,
                    category=excluded.category,
                    threat=excluded.threat,
                    triggers=excluded.triggers,
                    owner_user_id=excluded.owner_user_id,
                    status=excluded.status,
                    identified_at=excluded.identified_at,
                    status_changed_at=excluded.status_changed_at,
                    response_at=excluded.response_at,
                    occurred_at=excluded.occurred_at,
                    mitigation_plan=excluded.mitigation_plan,
                    document_url=excluded.document_url,
                    impact_cost=excluded.impact_cost,
                    impact_time=excluded.impact_time,
                    impact_scope=excluded.impact_scope,
                    impact_quality=excluded.impact_quality,
                    version=excluded.version,
                    is_deleted=excluded.is_deleted,
                    updated_at=excluded.updated_at,
                    dirty=0
                    """,
                    (
                        rid, project_id,
                        title, p, i,
                        code, description, category, threat, triggers,
                        owner_user_id, status,
                        identified_at, status_changed_at, response_at, occurred_at,
                        mitigation_plan, document_url,
                        impact_cost, impact_time, impact_scope, impact_quality,
                        ver, is_del, upd,
                    ),
                )

        self.conn.commit()

    def apply_pull_opportunities(self, project_id: str, server_opps: List[Dict[str, Any]]) -> None:
        pending_ids = {
            r["entity_id"]
            for r in self.conn.execute(
                "SELECT entity_id FROM outbox WHERE project_id=? AND entity='opportunity' AND status='pending';",
                (project_id,),
            ).fetchall()
        }

        cur = self.conn.cursor()
        for o in server_opps:
            oid = str(o["id"])

            title = str(o.get("title") or "")
            p = int(o.get("probability") or 1)
            i = int(o.get("impact") or 1)

            code = o.get("code")
            description = o.get("description")
            category = o.get("category")
            threat = o.get("threat")
            triggers = o.get("triggers")
            owner_user_id = o.get("owner_user_id")
            status = str(o.get("status") or "concept")

            identified_at = o.get("identified_at")
            status_changed_at = o.get("status_changed_at")
            response_at = o.get("response_at")
            occurred_at = o.get("occurred_at")
            mitigation_plan = o.get("mitigation_plan")
            document_url = o.get("document_url")
            impact_cost = o.get("impact_cost")
            impact_time = o.get("impact_time")
            impact_scope = o.get("impact_scope")
            impact_quality = o.get("impact_quality")

            ver = int(o.get("version") or 0)
            is_del = 1 if bool(o.get("is_deleted")) else 0
            upd = str(o.get("updated_at") or "")

            if oid in pending_ids:
                cur.execute("UPDATE opportunities SET version=?, updated_at=? WHERE id=?", (ver, upd, oid))
            else:
                cur.execute(
                    """
                    INSERT INTO opportunities (
                        id, project_id,
                        title, probability, impact,
                        code, description, category, threat, triggers,
                        owner_user_id, status,
                        identified_at, status_changed_at, response_at, occurred_at,
                        mitigation_plan, document_url,
                        impact_cost, impact_time, impact_scope, impact_quality,
                        version, is_deleted, updated_at, dirty
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    title=excluded.title,
                    probability=excluded.probability,
                    impact=excluded.impact,
                    code=excluded.code,
                    description=excluded.description,
                    category=excluded.category,
                    threat=excluded.threat,
                    triggers=excluded.triggers,
                    owner_user_id=excluded.owner_user_id,
                    status=excluded.status,
                    identified_at=excluded.identified_at,
                    status_changed_at=excluded.status_changed_at,
                    response_at=excluded.response_at,
                    occurred_at=excluded.occurred_at,
                    mitigation_plan=excluded.mitigation_plan,
                    document_url=excluded.document_url,
                    impact_cost=excluded.impact_cost,
                    impact_time=excluded.impact_time,
                    impact_scope=excluded.impact_scope,
                    impact_quality=excluded.impact_quality,
                    version=excluded.version,
                    is_deleted=excluded.is_deleted,
                    updated_at=excluded.updated_at,
                    dirty=0
                    """,
                    (
                        oid, project_id,
                        title, p, i,
                        code, description, category, threat, triggers,
                        owner_user_id, status,
                        identified_at, status_changed_at, response_at, occurred_at,
                        mitigation_plan, document_url,
                        impact_cost, impact_time, impact_scope, impact_quality,
                        ver, is_del, upd,
                    ),
                )

        self.conn.commit()

    def apply_pull_assessments(self, project_id: str, server_assessments: List[Dict[str, Any]]) -> None:
        pending_ids = {
            r["entity_id"]
            for r in self.conn.execute(
                "SELECT entity_id FROM outbox WHERE project_id=? AND entity='assessment' AND status='pending';",
                (project_id,),
            ).fetchall()
        }

        cur = self.conn.cursor()
        for a in server_assessments:
            aid = str(a["id"])
            rid = str(a["risk_id"])
            assessor = str(a.get("assessor_user_id") or "")
            p = int(a.get("probability") or 1)
            i = int(a.get("impact") or 1)
            score = int(a.get("score") or (p * i))
            notes = str(a.get("notes") or "")
            ver = int(a.get("version") or 0)
            is_del = 1 if bool(a.get("is_deleted")) else 0
            upd = str(a.get("updated_at") or "")

            if aid in pending_ids:
                cur.execute(
                    "UPDATE assessments SET version=?, updated_at=? WHERE id=?;",
                    (ver, upd, aid),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO assessments (id, project_id, risk_id, assessor_user_id, probability, impact, score, notes,
                                            version, is_deleted, updated_at, dirty)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    risk_id=excluded.risk_id,
                    assessor_user_id=excluded.assessor_user_id,
                    probability=excluded.probability,
                    impact=excluded.impact,
                    score=excluded.score,
                    notes=excluded.notes,
                    version=excluded.version,
                    is_deleted=excluded.is_deleted,
                    updated_at=excluded.updated_at,
                    dirty=0
                    """,
                    (aid, project_id, rid, assessor, p, i, score, notes, ver, is_del, upd),
                )

        self.conn.commit()
