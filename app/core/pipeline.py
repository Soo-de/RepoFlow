import asyncio
import shutil
import logging
from collections.abc import Callable

from app.core.repo_service import clone, CloneError
from app.core.repo_analysis import analyze
from app.core.platform_detect import detect as detect_platform
from app.core.pipeline_model import PipelineResult

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, str], None]


async def execute(
    repo_url: str,
    pat: str,
    platform: str,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    workspace = None

    async def _report(stage: str, message: str) -> None:
        if on_progress:
            on_progress(stage, message)
        # Give the event loop time to flush SSE events to the client
        await asyncio.sleep(0.05)

    try:
        # --- Stage 1: Clone ---
        await _report("cloning", "Cloning repository")
        repo_dir = await clone(repo_url, pat)
        workspace = repo_dir.parent
        await _report("cloning", "Repository cloned successfully")

        # --- Stage 2: Analyze ---
        await _report("analyzing", "Analyzing project structure")
        analysis = analyze(repo_dir)
        await _report("analyzing", f"Detected: {analysis.primary_language} ({analysis.dependency_manager})")
        if analysis.test_framework:
            await _report("analyzing", f"Test framework: {analysis.test_framework}")
        if analysis.services_needed:
            await _report("analyzing", f"Services: {', '.join(analysis.services_needed)}")
        await _report("analyzing", "Analysis complete")

        # --- Stage 3: Generate (stub until Phase 4 — LLM integration) ---
        detected_platform = detect_platform(analysis.existing_pipeline_files, platform)
        await _report("generating", f"Target platform: {detected_platform.value}")
        await _report("generating", "Pipeline generation pending LLM integration")
        yaml_output = "# placeholder — real generation comes in Phase 4"

        # --- Stage 4: Validate (stub until Phase 4) ---
        await _report("validating", "Validation pending LLM integration")
        validation_errors: list[str] = []
        await _report("validating", "Validation complete")

        return PipelineResult.from_analysis(
            analysis=analysis,
            platform=detected_platform,
            yaml_output=yaml_output,
            validation_passed=len(validation_errors) == 0,
            validation_errors=validation_errors,
        )

    except CloneError:
        raise

    except Exception as e:
        logger.exception("Pipeline execution failed")
        raise RuntimeError(f"Pipeline failed: {e}") from e

    finally:
        if workspace and workspace.exists():
            logger.info("Cleaning up workspace %s", workspace)
            shutil.rmtree(workspace, ignore_errors=True)

