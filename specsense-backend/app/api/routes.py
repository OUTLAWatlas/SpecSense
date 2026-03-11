from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.project import Project
from app.models.requirement import Requirement, RequirementVersion
from app.schemas.requirement import (
    AnalysisResult,
    ProjectCreate,
    ProjectResponse,
    RequirementCreate,
    RequirementResponse,
    RequirementStatus,
    RequirementUpdate,
    RequirementVersionResponse,
)
from app.worker.tasks import analyze_requirement_task

router = APIRouter()


# ── Helpers ──────────────────────────────────────────────────

def _build_requirement_response(
    req: Requirement,
    version: RequirementVersion | None = None,
) -> RequirementResponse:
    """Build a RequirementResponse from ORM objects."""
    if version is None and req.versions:
        version = req.versions[-1]

    current_version = None
    if version is not None:
        current_version = RequirementVersionResponse.model_validate(version)

    return RequirementResponse(
        id=req.id,
        project_id=req.project_id,
        status=RequirementStatus(req.status),
        current_version=current_version,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


# ── Projects ─────────────────────────────────────────────────

@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


# ── Requirements ─────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/requirements",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    project_id: uuid.UUID,
    payload: RequirementCreate,
    db: Session = Depends(get_db),
) -> RequirementResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    requirement = Requirement(project_id=project_id)
    db.add(requirement)
    db.flush()  # populate requirement.id before inserting version

    version = RequirementVersion(
        requirement_id=requirement.id,
        text_content=payload.text_content,
        # version_number is set by the DB trigger
    )
    db.add(version)
    db.commit()
    db.refresh(requirement)
    db.refresh(version)

    # Fire async analysis
    analyze_requirement_task.delay(str(version.id))

    return _build_requirement_response(requirement, version)


@router.put(
    "/requirements/{req_id}",
    response_model=RequirementResponse,
)
def update_requirement(
    req_id: uuid.UUID,
    payload: RequirementUpdate,
    db: Session = Depends(get_db),
) -> RequirementResponse:
    requirement = db.get(Requirement, req_id)
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement {req_id} not found",
        )

    # Mark requirement as draft (triggers updated_at via DB trigger)
    requirement.status = "draft"

    new_version = RequirementVersion(
        requirement_id=req_id,
        text_content=payload.text_content,
        # version_number is set by the DB trigger
    )
    db.add(new_version)
    db.commit()
    db.refresh(requirement)
    db.refresh(new_version)

    # Fire async analysis for the new version
    analyze_requirement_task.delay(str(new_version.id))

    return _build_requirement_response(requirement, new_version)


# ── Analysis ─────────────────────────────────────────────────

@router.get(
    "/requirements/{req_id}/analysis",
    response_model=AnalysisResult,
)
def get_analysis(
    req_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AnalysisResult:
    requirement = db.get(Requirement, req_id)
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement {req_id} not found",
        )

    if not requirement.versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No versions exist for this requirement",
        )

    latest = requirement.versions[-1]

    return AnalysisResult(
        requirement_id=req_id,
        version_id=latest.id,
        version_number=latest.version_number,
        quality_score=float(latest.quality_score) if latest.quality_score is not None else 0.0,
        status=RequirementStatus(requirement.status),
        analyzed_at=latest.created_at,
    )
