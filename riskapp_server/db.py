"""SQLAlchemy engine/session + ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
try:
    # SQLAlchemy 2.x generic type (works across SQLite/Postgres).
    from sqlalchemy.types import Uuid as SAUuid
except Exception:  # pragma: no cover
    try:
        from sqlalchemy import Uuid as SAUuid
    except Exception:  # pragma: no cover
        # Fallback for older SQLAlchemy.
        from sqlalchemy.dialects.postgresql import UUID as SAUuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .core.config import (
    AUTO_CREATE_SCHEMA,
    DATABASE_URL,
    DB_MAX_OVERFLOW,
    DB_POOL_RECYCLE,
    DB_POOL_SIZE,
    DB_STATEMENT_TIMEOUT_MS,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


_engine_kwargs: dict = {"pool_pre_ping": True}

if DATABASE_URL.startswith("sqlite"):
    # Needed for FastAPI/Uvicorn threading model.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update(
        {
            "pool_recycle": DB_POOL_RECYCLE,
            "pool_size": DB_POOL_SIZE,
            "max_overflow": DB_MAX_OVERFLOW,
        }
    )
    if DB_STATEMENT_TIMEOUT_MS and "postgresql" in DATABASE_URL:
        _engine_kwargs.setdefault("connect_args", {})
        _engine_kwargs["connect_args"].update(
            {"options": f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS}"}
        )

engine = create_engine(DATABASE_URL, **_engine_kwargs)


if "postgresql" in DATABASE_URL and DB_STATEMENT_TIMEOUT_MS:

    @event.listens_for(engine, "connect")
    def _set_statement_timeout(dbapi_conn, _):
        # Apply per-connection to guard against pathological slow queries.
        # (Milliseconds; 0 disables.)
        cur = dbapi_conn.cursor()
        cur.execute("SET statement_timeout = %s", (int(DB_STATEMENT_TIMEOUT_MS),))
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Dev convenience: auto-create tables when migrations are not used.
    # In production, use migrations (e.g., Alembic) and set AUTO_CREATE_SCHEMA=0.
    if AUTO_CREATE_SCHEMA:
        Base.metadata.create_all(bind=engine)


class Role(str, Enum):
    admin = "admin"
    manager = "manager"
    member = "member"
    viewer = "viewer"


class SyncMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )

    def soft_delete(self, now: datetime) -> None:
        self.is_deleted = True
        self.updated_at = now
        self.version = int(self.version) + 1
        if hasattr(self, "change_status"):
            self.change_status("deleted", now)


class RiskStatus(str, Enum):
    concept = "concept"
    active = "active"
    closed = "closed"
    deleted = "deleted"
    happened = "happened"


class SyncReceipt(Base):
    __tablename__ = "sync_receipts"
    # This table uses change_id as its identifier; don't inherit Base.id.
    id = None
    __table_args__ = (
        # Idempotency key: allow different users/projects to have different change_ids.
        UniqueConstraint("change_id", "user_id", "project_id", name="uq_sync_receipt"),
        Index("ix_sync_receipts_project_processed", "project_id", "processed_at"),
    )

    change_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("projects.id"), index=True, nullable=False
    )

    entity: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(SAUuid(as_uuid=True), index=True)
    op: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    processed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_project_ts", "project_id", "ts"),)

    ts: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, index=True, nullable=False
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("projects.id"), index=True, nullable=False
    )

    change_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), index=True, nullable=False
    )
    entity: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), index=True, nullable=False
    )
    op: Mapped[str] = mapped_column(String(20), nullable=False)

    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Project(Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )


class ItemBaseMixin(SyncMixin):
    project_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    probability: Mapped[int] = mapped_column(Integer, default=1)
    impact: Mapped[int] = mapped_column(Integer, default=1)
    impact_cost: Mapped[int | None] = mapped_column(Integer)
    impact_time: Mapped[int | None] = mapped_column(Integer)
    impact_scope: Mapped[int | None] = mapped_column(Integer)
    impact_quality: Mapped[int | None] = mapped_column(Integer)
    code: Mapped[str | None] = mapped_column(String(60), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(120), index=True)
    threat: Mapped[str | None] = mapped_column(Text)
    triggers: Mapped[str | None] = mapped_column(Text)
    mitigation_plan: Mapped[str | None] = mapped_column(Text)
    document_url: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default=RiskStatus.concept.value, nullable=False, index=True
    )
    identified_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    response_at: Mapped[datetime | None] = mapped_column(DateTime)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime)
    score: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    def change_status(self, new_status: str, now: datetime) -> None:
        if self.status != new_status:
            self.status = new_status
            self.status_changed_at = now
            if new_status == "happened":
                self.occurred_at = now


class Item(Base, ItemBaseMixin):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_items_project_code"),
        Index(
            "ix_items_project_type_deleted_score",
            "project_id",
            "type",
            "is_deleted",
            "score",
        ),
        Index("ix_items_project_type_updated", "project_id", "type", "updated_at"),
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)


class AssessmentMixin(SyncMixin):
    assessor_user_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    probability: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Assessment(Base, AssessmentMixin):
    __tablename__ = "assessments"
    __table_args__ = (
        UniqueConstraint("item_id", "assessor_user_id", name="uq_item_assessor"),
        Index("ix_assessments_item_updated", "item_id", "updated_at"),
        Index("ix_assessments_assessor_updated", "assessor_user_id", "updated_at"),
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("items.id"), nullable=False, index=True
    )

    @property
    def risk_id(self) -> uuid.UUID:  # client/API compatibility
        return self.item_id


class ActionKind(str, Enum):
    mitigation = "mitigation"
    contingency = "contingency"
    exploit = "exploit"


class ActionStatus(str, Enum):
    open = "open"
    doing = "doing"
    done = "done"


class Action(Base, SyncMixin):
    __tablename__ = "actions"
    __table_args__ = (
        Index(
            "ix_actions_project_deleted_updated",
            "project_id",
            "is_deleted",
            "updated_at",
        ),
        Index("ix_actions_project_item", "project_id", "item_id"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("items.id"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ActionStatus.open.value, index=True
    )

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"
    __table_args__ = (
        Index(
            "ix_score_snapshots_project_kind_captured",
            "project_id",
            "kind",
            "captured_at",
        ),
        Index("ix_score_snapshots_batch_score", "batch_id", "score"),
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), index=True, nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)

    project_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("projects.id"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    item_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)

    probability: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(
        SAUuid(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False
    )
