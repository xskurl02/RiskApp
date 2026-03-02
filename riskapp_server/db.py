"""SQLAlchemy engine/session + ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .core.config import DATABASE_URL


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


class Role(str, Enum):
    admin = "admin"
    manager = "manager"
    member = "member"
    viewer = "viewer"


class SyncMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

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
    __table_args__ = (
        # Idempotency key: allow different users/projects to have different change_ids.
        UniqueConstraint("change_id", "user_id", "project_id", name="uq_sync_receipt"),
    )

    change_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True, nullable=False)

    entity: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    op: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    processed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True, nullable=False)

    change_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    entity: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    op: Mapped[str] = mapped_column(String(20), nullable=False)

    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)


class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Project(Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_user"),)

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ItemBaseMixin(SyncMixin):
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
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
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default=RiskStatus.concept.value, nullable=False, index=True)
    identified_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)
    status_changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    response_at: Mapped[datetime | None] = mapped_column(DateTime)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime)
    score: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    def change_status(self, new_status: str, now: datetime) -> None:
        if self.status != new_status:
            self.status = new_status
            self.status_changed_at = now
            if new_status == "happened":
                self.occurred_at = now


class Risk(Base, ItemBaseMixin):
    __tablename__ = "risks"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_risks_project_code"),)


class Opportunity(Base, ItemBaseMixin):
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_opps_project_code"),)


class AssessmentMixin(SyncMixin):
    assessor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    probability: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)

class RiskAssessment(Base, AssessmentMixin):
    __tablename__ = "risk_assessments"
    __table_args__ = (UniqueConstraint("risk_id", "assessor_user_id", name="uq_risk_assessor"),)
    risk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("risks.id"), nullable=False, index=True)

class OpportunityAssessment(Base, AssessmentMixin):
    __tablename__ = "opportunity_assessments"
    __table_args__ = (UniqueConstraint("opportunity_id", "assessor_user_id", name="uq_opp_assessor"),)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False, index=True)

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
        CheckConstraint(
            "((risk_id IS NOT NULL)::int + (opportunity_id IS NOT NULL)::int) = 1",
            name="ck_action_exactly_one_target",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)

    risk_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("risks.id"), index=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunities.id"), index=True)

    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ActionStatus.open.value, index=True)

    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)


class ScoreSnapshot(Base):
    __tablename__ = "score_snapshots"

    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)

    probability: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)