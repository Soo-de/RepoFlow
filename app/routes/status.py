from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import HTMLResponse, Response

from app import templates
from app.jobs import store
from app.jobs.store import JobStatus

router = APIRouter(tags=["status"])


@router.get("/status/{job_id}", response_class=HTMLResponse)
async def job_status(
    request: Request,
    job_id: str,
    hx_request: str | None = Header(default=None, alias="HX-Request"),
):
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # If the job is complete or failed, handle final rendering
    if job.status == JobStatus.DONE:
        if hx_request:
            # Let HTMX redirect the full page to show the final result
            return Response(headers={"HX-Redirect": f"/status/{job_id}"})
        yaml_output = job.result.get("yaml", "") if job.result else ""
        return templates.TemplateResponse(request, "result.html", context={"yaml_output": yaml_output})

    if job.status == JobStatus.FAILED:
        if hx_request:
            return Response(headers={"HX-Redirect": f"/status/{job_id}"})
        # For simplicity in MVP, we can render the error on the result template
        error_msg = f"Generation failed: {job.error}"
        return templates.TemplateResponse(request, "result.html", context={"yaml_output": error_msg})

    # If still processing, check if it's an HTMX poll or a full page load
    if hx_request:
        # Return just the inner status-card HTML (HTMX swaps this innerHTML)
        loader_div = "" if job.status in [JobStatus.DONE, JobStatus.FAILED] else '<div class="loader"></div>'
        html_content = f"""
        <p class="job-id">Job: <code>{job_id[:8]}</code></p>
        <div class="status-indicator">
            <span class="badge badge-{job.status.value}">{job.status.value}</span>
        </div>
        {loader_div}
        """
        return HTMLResponse(content=html_content)

    return templates.TemplateResponse(request, "status.html", context={
        "job_id": job_id,
        "status": job.status.value,
    })

