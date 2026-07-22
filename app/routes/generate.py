import uuid
import asyncio
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from app import templates
from app.jobs import store, run_job
from app.jobs.store import JobStatus, STAGE_ORDER

router = APIRouter(tags=["generate"])

STAGES = ["cloning", "analyzing", "generating", "validating"]


@router.get("/", response_class=RedirectResponse)
async def index():
    return RedirectResponse(url="/generate")


@router.get("/generate", response_class=HTMLResponse)
async def generate_view(request: Request):
    jobs = store.list_all()
    job_rows = [_render_job_row(job_id, job) for job_id, job in reversed(list(jobs.items()))]
    return templates.TemplateResponse(request, "index.html", context={"job_rows": job_rows})


@router.post("/generate", response_class=HTMLResponse)
async def generate_pipeline(
    request: Request,
    repo_url: str = Form(...),
    pat: str = Form(""),
    platform: str = Form("auto"),
):
    job_id = str(uuid.uuid4())
    store.create(job_id, repo_url=repo_url)
    asyncio.create_task(run_job(job_id, repo_url, pat, platform))

    job = store.get(job_id)
    return HTMLResponse(content=_render_job_row(job_id, job))


def _render_mini_stepper(status: JobStatus, logs: list) -> str:
    if status == JobStatus.DONE:
        items = []
        for i, stage in enumerate(STAGES):
            items.append(f'<div class="mini-step completed" title="{stage}"></div>')
            if i < len(STAGES) - 1:
                items.append('<div class="mini-connector completed"></div>')
        return f'<div class="mini-stepper">{"".join(items)}</div>'

    if status == JobStatus.FAILED:
        failed_stage = logs[-1].stage if logs else "cloning"
        failed_idx = STAGES.index(failed_stage) if failed_stage in STAGES else 0

        items = []
        for i, stage in enumerate(STAGES):
            if i < failed_idx:
                items.append(f'<div class="mini-step completed" title="{stage}"></div>')
            elif i == failed_idx:
                items.append(f'<div class="mini-step failed" title="{stage} (failed)"></div>')
            else:
                items.append(f'<div class="mini-step" title="{stage}"></div>')

            if i < len(STAGES) - 1:
                conn_class = "completed" if i < failed_idx else ("failed" if i == failed_idx else "")
                items.append(f'<div class="mini-connector {conn_class}"></div>')
        return f'<div class="mini-stepper">{"".join(items)}</div>'

    curr_stage = status.value
    curr_idx = STAGES.index(curr_stage) if curr_stage in STAGES else -1

    items = []
    for i, stage in enumerate(STAGES):
        if curr_idx != -1 and i < curr_idx:
            step_class = "completed"
        elif curr_idx != -1 and i == curr_idx:
            step_class = "active"
        else:
            step_class = ""
        items.append(f'<div class="mini-step {step_class}" title="{stage}"></div>')

        if i < len(STAGES) - 1:
            conn_class = "completed" if (curr_idx != -1 and i < curr_idx) else ""
            items.append(f'<div class="mini-connector {conn_class}"></div>')

    return f'<div class="mini-stepper">{"".join(items)}</div>'


def _render_job_row(job_id: str, job) -> str:
    repo_display = job.repo_url.rstrip("/").split("/")[-1] if job.repo_url else "unknown"
    status = job.status
    badge_class = "done" if status == JobStatus.DONE else ("failed" if status == JobStatus.FAILED else "running")
    status_label = status.value

    stepper_html = _render_mini_stepper(status, job.logs)

    download_btn = ""
    if status == JobStatus.DONE:
        download_btn = f'<a href="/jobs/{job_id}/download" class="btn-icon" title="Download YAML" onclick="event.stopPropagation();">↓</a>'

    hx_trigger = "none" if status in (JobStatus.DONE, JobStatus.FAILED) else "every 1s"

    return f"""
    <div class="job-row" onclick="window.location='/jobs/{job_id}'"
         hx-get="/jobs/queue/row/{job_id}" hx-trigger="{hx_trigger}"
         hx-swap="outerHTML" id="job-{job_id}">
        <div class="job-row-info">
            <span class="job-row-repo">{repo_display}</span>
            <span class="job-row-id">{job_id[:8]}</span>
        </div>
        <div class="job-row-progress">
            {stepper_html}
        </div>
        <div class="job-row-status">
            <span class="badge badge-{badge_class}">{status_label}</span>
            {download_btn}
        </div>
    </div>
    """

