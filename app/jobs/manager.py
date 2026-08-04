import logging

from app.jobs import store
from app.jobs.store import JobStatus
from app.core.pipeline import execute as run_pipeline
from app.core.repo_service import CloneError
from app.core.readiness import ReadinessError

logger = logging.getLogger(__name__)


async def run_job(
    job_id: str,
    repo_url: str,
    pat: str,
    platform: str,
) -> None:
    current_stage = "cloning"

    def on_progress(stage: str, message: str) -> None:
        nonlocal current_stage
        current_stage = stage
        store.update(job_id, status=JobStatus(stage))
        store.append_log(job_id, stage, message)

    try:
        result = await run_pipeline(
            repo_url=repo_url,
            pat=pat,
            platform=platform,
            on_progress=on_progress,
        )
        store.append_log(job_id, "done", "Pipeline generation complete")
        store.update(
            job_id,
            status=JobStatus.DONE,
            result={
                "yaml": result.yaml_output,
                "dockerfile": result.dockerfile_output,
                "dockerfile_generated": result.dockerfile_generated,
                "platform": result.platform,
                "validation_passed": result.validation_passed,
                "validation_errors": result.validation_errors,
                "analysis": result.analysis,
            },
        )
        logger.info("Job %s: complete", job_id)

    except CloneError as e:
        logger.warning("Job %s: clone failed — %s", job_id, e)
        store.append_log(job_id, "cloning", str(e))
        store.update(job_id, status=JobStatus.FAILED, error=str(e), failed_stage="cloning")

    except ReadinessError as e:
        blocker_lines = "\n".join(f"• {b}" for b in e.blockers)
        user_message = f"Pipeline generation cannot continue:\n{blocker_lines}"
        logger.warning("Job %s: readiness check failed — %s", job_id, e)
        store.append_log(job_id, "analyzing", user_message)
        store.update(job_id, status=JobStatus.FAILED, error=user_message, failed_stage="analyzing")

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        store.append_log(job_id, current_stage, str(e))
        store.update(job_id, status=JobStatus.FAILED, error=str(e), failed_stage=current_stage)

