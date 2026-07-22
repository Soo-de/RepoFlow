from pydantic import BaseModel


class GenerateRequest(BaseModel):
    repo_url: str
    pat: str = ""
    platform: str = "auto"
