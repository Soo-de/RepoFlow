# core package — pure business logic, no framework awareness
from app.core.repo_service import clone, CloneError
from app.core.repo_analysis import analyze, RepoAnalysis
from app.core.platform_detect import detect as detect_platform, Platform
from app.core.pipeline_model import PipelineResult
from app.core.pipeline import execute

__all__ = [
    "clone", "CloneError",
    "analyze", "RepoAnalysis",
    "detect_platform", "Platform",
    "PipelineResult",
    "execute",
]
