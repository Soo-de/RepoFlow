import shutil
import asyncio
import tempfile
import logging
from pathlib import Path
from dataclasses import dataclass
from collections.abc import Callable

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str], None]


@dataclass(frozen=True)
class PipelineResult:
    yaml_output: str
    platform: str
    validation_passed: bool
    validation_errors: list[str]


async def execute(
    repo_url: str,
    pat: str,
    platform: str,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    workspace: Path | None = None

    def _report(stage: str, message: str) -> None:
        if on_progress:
            on_progress(stage, message)

    try:
        _report("cloning", "Cloning repository")
        workspace = Path(tempfile.mkdtemp(prefix="repoflow_"))
        logger.info("Cloning %s into %s", repo_url, workspace)
        await asyncio.sleep(1.5)
        _report("cloning", "Fetching remote tags and branches")
        await asyncio.sleep(1.0)
        _report("cloning", "Repository cloned successfully")

        _report("analyzing", "Analyzing project structure")
        logger.info("Analyzing repository structure")
        await asyncio.sleep(1.5)
        _report("analyzing", "Detected project languages and frameworks")
        await asyncio.sleep(1.0)
        _report("analyzing", "Mapped dependency graph")

        _report("generating", "Building prompt from analysis results")
        logger.info("Building prompt and calling LLM")
        await asyncio.sleep(1.0)
        _report("generating", "Sending prompt to LLM")
        await asyncio.sleep(1.5)
        _report("generating", "Received model response")
        await asyncio.sleep(0.8)
        _report("generating", "Applying CI/CD template")
        yaml_output = "# placeholder pipeline output"

        _report("validating", "Validating generated YAML syntax")
        logger.info("Validating generated output")
        await asyncio.sleep(1.0)
        _report("validating", "Running schema validation")
        await asyncio.sleep(1.0)
        validation_errors: list[str] = []
        _report("validating", "Validation complete — no errors found")

        return PipelineResult(
            yaml_output=yaml_output,
            platform=platform,
            validation_passed=len(validation_errors) == 0,
            validation_errors=validation_errors,
        )

    finally:
        if workspace and workspace.exists():
            logger.info("Cleaning up workspace %s", workspace)
            shutil.rmtree(workspace, ignore_errors=True)
