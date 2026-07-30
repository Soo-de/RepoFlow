import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from sse_starlette import EventSourceResponse

from app import templates
from app.jobs import store
from app.jobs.store import JobStatus
from app.routes.generate import _render_job_row

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/queue/row/{job_id}", response_class=HTMLResponse)
async def queue_row(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return HTMLResponse(content=_render_job_row(job_id, job))


@router.get("/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return templates.TemplateResponse(request, "detail.html", context={
        "job_id": job_id,
        "job": job,
    })


@router.get("/{job_id}/stream")
async def job_stream(job_id: str, cursor: int = 0):
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        async for entry in store.subscribe(job_id, cursor=cursor):
            yield {
                "event": "log",
                "data": json.dumps({
                    "timestamp": entry.timestamp,
                    "stage": entry.stage,
                    "message": entry.message,
                }),
            }

        final_job = store.get(job_id)
        payload = {"status": final_job.status.value}
        if final_job.status == JobStatus.DONE and final_job.result:
            payload["yaml"] = final_job.result.get("yaml") or ""
            payload["dockerfile"] = final_job.result.get("dockerfile") or ""
        if final_job.status == JobStatus.FAILED:
            payload["error"] = final_job.error or "Unknown error"
            payload["failed_stage"] = final_job.failed_stage or "cloning"
        yield {"event": "complete", "data": json.dumps(payload)}

    return EventSourceResponse(event_generator())


@router.get("/{job_id}/download")
async def job_download(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.result:
        raise HTTPException(status_code=400, detail="Job not complete")

    yaml_content = job.result.get("yaml", "")
    repo_name = job.repo_url.rstrip("/").split("/")[-1] if job.repo_url else "pipeline"
    filename = f"{repo_name}-pipeline.yml"

    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{job_id}/download/dockerfile")
async def job_download_dockerfile(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.result:
        raise HTTPException(status_code=400, detail="Job not complete")

    dockerfile_content = job.result.get("dockerfile", "")
    if not dockerfile_content:
        raise HTTPException(status_code=404, detail="No Dockerfile available")

    return Response(
        content=dockerfile_content,
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="Dockerfile"'},
    )
