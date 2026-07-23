import logging
from enum import Enum

logger = logging.getLogger(__name__)


class Platform(str, Enum):
    GITHUB_ACTIONS = "github_actions"
    AZURE_PIPELINES = "azure_pipelines"


PLATFORM_DETECTION_MAP: dict[str, Platform] = {
    ".github/workflows": Platform.GITHUB_ACTIONS,
    "azure-pipelines.yml": Platform.AZURE_PIPELINES,
    ".azure-pipelines": Platform.AZURE_PIPELINES,
}

DEFAULT_PLATFORM = Platform.AZURE_PIPELINES


def detect(existing_pipeline_files: list[str], user_choice: str = "auto") -> Platform:
    """Determine the target CI/CD platform.

    Priority:
    1. Explicit user choice (not "auto")
    2. Auto-detect from existing CI config files
    3. Default to Azure Pipelines
    """
    if user_choice != "auto":
        try:
            return Platform(user_choice)
        except ValueError:
            logger.warning("Unknown platform '%s', falling back to auto-detect", user_choice)

    for file_path in existing_pipeline_files:
        for pattern, platform in PLATFORM_DETECTION_MAP.items():
            if file_path.startswith(pattern):
                logger.info("Detected platform: %s (from %s)", platform.value, file_path)
                return platform

    logger.info("No CI config found, using default: %s", DEFAULT_PLATFORM.value)
    return DEFAULT_PLATFORM
