import time
import random

from app.core.celery_app import celery_app


@celery_app.task(bind=True, name="analyze_requirement_task")
def analyze_requirement_task(self, version_id: str) -> dict:
    """Analyse a requirement version and return a mock quality score.

    In production this will call the NLP / LLM pipeline.
    For now it sleeps for 2 seconds and returns a random score.
    """
    self.update_state(state="ANALYZING", meta={"version_id": version_id})

    time.sleep(2)

    quality_score: float = round(random.uniform(0.0, 100.0), 2)

    return {
        "version_id": version_id,
        "quality_score": quality_score,
        "status": "analyzed",
    }
