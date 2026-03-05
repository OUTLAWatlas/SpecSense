from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────

class RequirementStatus(str, Enum):
    DRAFT = "draft"
    ANALYZED = "analyzed"
    VALIDATED = "validated"
    STALE = "stale"


# ── Project Schemas ──────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Requirement Schemas ──────────────────────────────────────

class RequirementCreate(BaseModel):
    text_content: str = Field(..., min_length=1)


class RequirementUpdate(BaseModel):
    text_content: str = Field(..., min_length=1)


class RequirementVersionResponse(BaseModel):
    id: uuid.UUID
    requirement_id: uuid.UUID
    version_number: int
    text_content: str
    quality_score: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class RequirementResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    status: RequirementStatus
    current_version: Optional[RequirementVersionResponse]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Analysis Schemas ─────────────────────────────────────────

class AnalysisResult(BaseModel):
    requirement_id: uuid.UUID
    version_id: uuid.UUID
    version_number: int
    quality_score: float
    status: RequirementStatus
    analyzed_at: datetime
