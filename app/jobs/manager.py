"""
Async job runner — thin wrapper that connects the pipeline facade to the job store.

Called via asyncio.create_task() from routes/generate.py.
Delegates all real work to core/pipeline.execute() and translates
progress callbacks into store updates for HTMX polling.
"""

import logging

from app.jobs import store
from app.jobs.store import JobStatus
from app.core.pipeline import execute as run_pipeline

logger = logging.getLogger(__name__)


async def run_job(
    job_id: str,
    repo_url: str,
    pat: str,
    platform: str,
) -> None:
    """Launch the pipeline and map its lifecycle to the job store."""
    try:
        result = await run_pipeline(
            repo_url=repo_url,
            pat=pat,
            platform=platform,
            on_progress=lambda stage: store.update(job_id, status=JobStatus(stage)),
        )
        store.update(
            job_id,
            status=JobStatus.DONE,
            result={
                "yaml": result.yaml_output,
                "platform": result.platform,
                "validation_passed": result.validation_passed,
                "validation_errors": result.validation_errors,
            },
        )
        logger.info("Job %s: complete", job_id)

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        store.update(job_id, status=JobStatus.FAILED, error=str(e))
