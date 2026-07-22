from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: str | None = None
