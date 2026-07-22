from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app import templates

router = APIRouter(tags=["status"])


@router.get("/status/{job_id}", response_class=HTMLResponse)
async def job_status(request: Request, job_id: str):
    return templates.TemplateResponse(request, "status.html", context={
        "job_id": job_id,
        "status": "pending",
    })
