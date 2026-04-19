from __future__ import annotations

import logging
import uuid
from typing import Any

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models import RequirementVersion
from app.services.analyzer import RequirementAnalyzer


logger = logging.getLogger(__name__)
analyzer = RequirementAnalyzer()


@celery_app.task(bind=True, name="analyze_requirement_task")
def analyze_requirement_task(self: Any, version_id: str) -> dict[str, Any]:
    """Analyze a requirement version, persist the score, and return results."""
    self.update_state(state="ANALYZING", meta={"version_id": version_id})

    version_uuid = uuid.UUID(version_id)

    with SessionLocal() as db:
        version = db.get(RequirementVersion, version_uuid)
        if version is None:
            logger.error("RequirementVersion %s was not found", version_id)
            return {"version_id": version_id, "quality_score": None, "has_passive_voice": False, "weak_words": []}

        analysis = analyzer.analyze_syntax(version.text_content)

        version.quality_score = float(analysis["score"])
        db.commit()

    return {
        "version_id": version_id,
        "quality_score": float(analysis["score"]),
        "has_passive_voice": bool(analysis["has_passive_voice"]),
        "weak_words": list(analysis["weak_words"]),
    }
