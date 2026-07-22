import asyncio
import logging
import tempfile
import shutil
from pathlib import Path
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.jobs import store
from app.jobs.store import JobStatus

logger = logging.getLogger(__name__)


@asynccontextmanager
async def temp_workspace() -> AsyncIterator[Path]:
    workspace = Path(tempfile.mkdtemp(prefix="repoflow_"))
    try:
        yield workspace
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


async def run_job(
    job_id: str,
    repo_url: str,
    pat: str,
    platform: str,
) -> None:
    try:
        async with temp_workspace() as workspace:
            store.update(job_id, status=JobStatus.CLONING)
            logger.info("Job %s: cloning %s", job_id, repo_url)
            await asyncio.sleep(0)

            store.update(job_id, status=JobStatus.ANALYZING)
            logger.info("Job %s: analyzing", job_id)
            await asyncio.sleep(0)

            store.update(job_id, status=JobStatus.GENERATING)
            logger.info("Job %s: generating pipeline", job_id)
            await asyncio.sleep(0)

            store.update(job_id, status=JobStatus.VALIDATING)
            logger.info("Job %s: validating output", job_id)
            await asyncio.sleep(0)

            store.update(
                job_id,
                status=JobStatus.DONE,
                result={"yaml": "# placeholder pipeline output"},
            )
            logger.info("Job %s: complete", job_id)

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        store.update(job_id, status=JobStatus.FAILED, error=str(e))
