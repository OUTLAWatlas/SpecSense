from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

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

# ── In-memory stores (replaced by DB in the next iteration) ──
_projects: dict[uuid.UUID, ProjectResponse] = {}
_requirements: dict[uuid.UUID, RequirementResponse] = {}
_versions: dict[uuid.UUID, RequirementVersionResponse] = {}
_analysis: dict[uuid.UUID, AnalysisResult] = {}


# ── Projects ─────────────────────────────────────────────────

@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(payload: ProjectCreate) -> ProjectResponse:
    now = datetime.now(tz=timezone.utc)
    project = ProjectResponse(
        id=uuid.uuid4(),
        name=payload.name,
        description=payload.description,
        created_at=now,
        updated_at=now,
    )
    _projects[project.id] = project
    return project


# ── Requirements ─────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/requirements",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_requirement(
    project_id: uuid.UUID,
    payload: RequirementCreate,
) -> RequirementResponse:
    if project_id not in _projects:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    now = datetime.now(tz=timezone.utc)
    req_id = uuid.uuid4()
    version_id = uuid.uuid4()

    version = RequirementVersionResponse(
        id=version_id,
        requirement_id=req_id,
        version_number=1,
        text_content=payload.text_content,
        quality_score=None,
        created_at=now,
    )
    _versions[version_id] = version

    requirement = RequirementResponse(
        id=req_id,
        project_id=project_id,
        status=RequirementStatus.DRAFT,
        current_version=version,
        created_at=now,
        updated_at=now,
    )
    _requirements[req_id] = requirement

    # Fire async analysis
    analyze_requirement_task.delay(str(version_id))

    return requirement


@router.put(
    "/requirements/{req_id}",
    response_model=RequirementResponse,
)
def update_requirement(
    req_id: uuid.UUID,
    payload: RequirementUpdate,
) -> RequirementResponse:
    requirement = _requirements.get(req_id)
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement {req_id} not found",
        )

    now = datetime.now(tz=timezone.utc)
    prev_version = requirement.current_version
    next_number = (prev_version.version_number + 1) if prev_version else 1
    version_id = uuid.uuid4()

    new_version = RequirementVersionResponse(
        id=version_id,
        requirement_id=req_id,
        version_number=next_number,
        text_content=payload.text_content,
        quality_score=None,
        created_at=now,
    )
    _versions[version_id] = new_version

    updated = requirement.model_copy(
        update={
            "current_version": new_version,
            "status": RequirementStatus.DRAFT,
            "updated_at": now,
        }
    )
    _requirements[req_id] = updated

    # Fire async analysis for the new version
    analyze_requirement_task.delay(str(version_id))

    return updated


# ── Analysis ─────────────────────────────────────────────────

@router.get(
    "/requirements/{req_id}/analysis",
    response_model=AnalysisResult,
)
def get_analysis(req_id: uuid.UUID) -> AnalysisResult:
    requirement = _requirements.get(req_id)
    if requirement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement {req_id} not found",
        )

    if req_id in _analysis:
        return _analysis[req_id]

    # Return a mock result when no real analysis has completed yet
    current = requirement.current_version
    if current is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No versions exist for this requirement",
        )

    mock = AnalysisResult(
        requirement_id=req_id,
        version_id=current.id,
        version_number=current.version_number,
        quality_score=current.quality_score or 0.0,
        status=requirement.status,
        analyzed_at=datetime.now(tz=timezone.utc),
    )
    return mock
