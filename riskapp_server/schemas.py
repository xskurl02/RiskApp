"""Pydantic request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .db import ActionKind, ActionStatus, RiskStatus, Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class AddMemberIn(BaseModel):
    user_email: EmailStr
    role: Role


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    role: Role
    created_at: datetime | None = None


class ProjectOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    created_by: uuid.UUID


class ItemShared(BaseModel):
    impact_cost: int | None = Field(default=None, ge=1, le=5)
    impact_time: int | None = Field(default=None, ge=1, le=5)
    impact_scope: int | None = Field(default=None, ge=1, le=5)
    impact_quality: int | None = Field(default=None, ge=1, le=5)
    code: str | None = None
    description: str | None = None
    category: str | None = None
    threat: str | None = None
    triggers: str | None = None
    mitigation_plan: str | None = None
    document_url: str | None = None
    owner_user_id: uuid.UUID | None = None
    status: RiskStatus | None = None
    identified_at: datetime | None = None
    response_at: datetime | None = None
    occurred_at: datetime | None = None


class ItemCreate(ItemShared):
    type: Literal["risk", "opportunity"]
    title: str
    probability: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)


class ItemUpdate(ItemShared):
    base_version: int | None = None
    title: str | None = None
    probability: int | None = Field(default=None, ge=1, le=5)
    impact: int | None = Field(default=None, ge=1, le=5)


class ItemOut(ItemShared, ORMModel):
    id: uuid.UUID
    type: Literal["risk", "opportunity"]
    project_id: uuid.UUID
    title: str
    probability: int
    impact: int
    score: int
    status_changed_at: datetime | None = None
    created_at: datetime
    created_by: uuid.UUID
    updated_at: datetime
    version: int
    is_deleted: bool


class ScoreReportOut(BaseModel):
    total: int
    project_total: int | None = None
    min_score: int | None = None
    max_score: int | None = None
    avg_score: float | None = None
    status_counts: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    owner_counts: dict[str, int] = Field(default_factory=dict)
    score_buckets: dict[str, int] = Field(default_factory=dict)


class AssessmentIn(BaseModel):
    base_version: int | None = None
    probability: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    notes: str | None = None


class AssessmentOut(ORMModel):
    id: uuid.UUID
    item_id: uuid.UUID
    assessor_user_id: uuid.UUID
    probability: int
    impact: int
    score: int
    notes: str | None
    created_at: datetime
    updated_at: datetime
    version: int
    is_deleted: bool


class MatrixResponse(BaseModel):
    kind: str
    probability_axis: list[int]
    impact_axis: list[int]
    risks: list[list[int]] | None = None
    opportunities: list[list[int]] | None = None


class ActionCreate(BaseModel):
    item_id: uuid.UUID
    kind: ActionKind
    title: str
    description: str | None = None
    owner_user_id: uuid.UUID | None = None


class ActionUpdate(BaseModel):
    kind: ActionKind | None = None
    title: str | None = None
    description: str | None = None
    status: ActionStatus | None = None
    owner_user_id: uuid.UUID | None = None


class ActionOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    item_id: uuid.UUID
    kind: ActionKind
    title: str
    description: str | None
    status: ActionStatus
    owner_user_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    version: int
    is_deleted: bool


class SnapshotCreateOut(BaseModel):
    batch_id: uuid.UUID
    captured_at: datetime
    risks: int = 0
    opportunities: int = 0


class TopItem(BaseModel):
    item_id: uuid.UUID
    title: str
    probability: int
    impact: int
    score: int


class TopBatch(BaseModel):
    batch_id: uuid.UUID
    captured_at: datetime
    top: list[TopItem]


class SyncPullRequest(BaseModel):
    project_id: uuid.UUID
    since: datetime


class SyncPullResponse(BaseModel):
    server_time: datetime
    items: list[ItemOut]
    actions: list[ActionOut]
    assessments: list[AssessmentOut]


class SyncChange(BaseModel):
    change_id: uuid.UUID
    entity: str
    op: str
    base_version: int | None = None
    record: dict


class SyncPushRequest(BaseModel):
    project_id: uuid.UUID
    changes: list[SyncChange]


class SyncPushResponse(BaseModel):
    accepted: int
    duplicates: int = 0
    duplicate_change_ids: list[str] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    server_time: datetime


# Sync payload validators (internal)


class SyncItemRecord(ItemShared):
    id: uuid.UUID
    title: str | None = None
    probability: int | None = Field(default=None, ge=1, le=5)
    impact: int | None = Field(default=None, ge=1, le=5)
    is_deleted: bool | None = None


class SyncActionRecord(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID | None = None
    kind: ActionKind | None = None
    title: str | None = None
    description: str | None = None
    status: ActionStatus | None = None
    owner_user_id: uuid.UUID | None = None
    is_deleted: bool | None = None


class SyncAssessmentRecord(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID | None = None
    probability: int | None = Field(default=None, ge=1, le=5)
    impact: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    is_deleted: bool | None = None
