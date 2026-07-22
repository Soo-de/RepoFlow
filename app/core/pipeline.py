"""
Pipeline facade — single entry point that orchestrates the entire generation lifecycle.

This is the only module that imports from other core/ modules. It chains them
in sequence (clone → analyze → generate → validate) inside a try/finally
block that guarantees workspace cleanup regardless of success or failure.

The facade is framework-agnostic: it knows nothing about jobs, stores, HTTP,
or HTMX. Progress is reported through an optional callback, and the result
is returned as a typed dataclass. This makes the full pipeline independently
testable without any infrastructure.

Callers:
  - jobs/manager.py (production — wires callback to job store)
  - tests/ (testing — passes None or a mock callback)
"""

import shutil
import tempfile
import logging
from pathlib import Path
from dataclasses import dataclass
from collections.abc import Callable, Awaitable

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None]


@dataclass(frozen=True)
class PipelineResult:
    """Immutable output of a successful pipeline run."""
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
    """
    Run the full pipeline: clone → analyze → generate → validate.

    Args:
        repo_url: Git repository URL to clone.
        pat: Personal access token for private repos (empty string if public).
        platform: Target CI/CD platform ("auto", "github_actions", "azure_pipelines").
        on_progress: Optional callback invoked at each stage transition.

    Returns:
        PipelineResult with the generated YAML and validation info.

    Raises:
        Exception: Any failure during the pipeline. Workspace is always cleaned up.
    """
    workspace: Path | None = None

    def _report(stage: str) -> None:
        if on_progress:
            on_progress(stage)

    try:
        # --- Stage 1: Clone ---
        _report("cloning")
        workspace = Path(tempfile.mkdtemp(prefix="repoflow_"))
        logger.info("Cloning %s into %s", repo_url, workspace)
        # TODO: wire core/repo_service.clone(repo_url, pat, workspace)

        # --- Stage 2: Analyze ---
        _report("analyzing")
        logger.info("Analyzing repository structure")
        # TODO: analysis = core/repo_analysis.analyze(workspace)

        # --- Stage 3: Generate ---
        _report("generating")
        logger.info("Building prompt and calling LLM")
        # TODO: prompt = core/prompt_builder.build(analysis, platform)
        # TODO: yaml_output = await core/llm_client.call(prompt)
        yaml_output = "# placeholder pipeline output"

        # --- Stage 4: Validate ---
        _report("validating")
        logger.info("Validating generated output")
        # TODO: errors = core/validation.validate(yaml_output, platform)
        validation_errors: list[str] = []

        return PipelineResult(
            yaml_output=yaml_output,
            platform=platform,
            validation_passed=len(validation_errors) == 0,
            validation_errors=validation_errors,
        )

    finally:
        # Transactional cleanup — remove cloned repo regardless of success or failure.
        # This block runs even if an exception is raised mid-pipeline.
        if workspace and workspace.exists():
            logger.info("Cleaning up workspace %s", workspace)
            shutil.rmtree(workspace, ignore_errors=True)
