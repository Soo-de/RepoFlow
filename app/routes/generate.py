import uuid
import asyncio
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from app import templates
from app.jobs import store, run_job

router = APIRouter(tags=["generate"])


@router.get("/", response_class=RedirectResponse)
async def index():
    return RedirectResponse(url="/generate")


@router.get("/generate", response_class=HTMLResponse)
async def generate_view(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.post("/generate")
async def generate_pipeline(
    repo_url: str = Form(...),
    pat: str = Form(""),
    platform: str = Form("auto"),
):
    job_id = str(uuid.uuid4())
    store.create(job_id)
    asyncio.create_task(run_job(job_id, repo_url, pat, platform))
    return RedirectResponse(url=f"/status/{job_id}", status_code=303)

