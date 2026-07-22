from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse

from app import templates

router = APIRouter(tags=["generate"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@router.post("/generate", response_class=HTMLResponse)
async def generate_pipeline(
    request: Request,
    repo_url: str = Form(...),
    pat: str = Form(""),
    platform: str = Form("auto"),
):
    return templates.TemplateResponse(request, "index.html", context={
        "message": "Pipeline generation will be wired in Phase 3.",
        "repo_url": repo_url,
        "platform": platform,
    })
