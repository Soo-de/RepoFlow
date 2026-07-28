import asyncio
import shutil
import logging
from collections.abc import Callable

from app.settings import settings
from app.core.repo_service import clone, CloneError
from app.core.repo_analysis import analyze
from app.core.platform_detect import detect as detect_platform
from app.core.pipeline_model import PipelineResult
from app.core.prompt_builder import PromptBuilder
from app.core.llm_client import LLMClient
from app.core.validation import PipelineValidator, strip_markdown_fences

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

        # --- Stage 3: Generate ---
        detected_platform = detect_platform(analysis.existing_pipeline_files, platform)
        await _report("generating", f"Target platform: {detected_platform.value}")
        await _report("generating", "Building LLM prompt template")

        prompt_builder = PromptBuilder()
        prompt = prompt_builder.build(detected_platform, analysis)

        await _report("generating", f"Calling LLM API (provider: {settings.llm_provider}) to generate pipeline YAML")
        llm_client = LLMClient(
            gemini_api_key=settings.gemini_api_key,
            groq_api_key=settings.groq_api_key,
            openai_api_key=settings.openai_api_key,
            provider=settings.llm_provider,
            gemini_model=settings.gemini_model,
            groq_model=settings.groq_model,
            openai_model=settings.openai_model,
        )
        try:
            raw_yaml_output = await llm_client.generate(prompt)
            await _report("generating", "Pipeline generation complete")

            # --- Stage 4: Validate and Self-Correct ---
            await _report("validating", "Validating generated YAML syntax and schema")
            validator = PipelineValidator()

            cleaned_yaml = strip_markdown_fences(raw_yaml_output)
            is_valid, errors = validator.validate(detected_platform, cleaned_yaml, services_needed=analysis.services_needed)

            max_retries = 5
            retry_count = 0


            while not is_valid and retry_count < max_retries:
                retry_count += 1
                await _report("validating", f"Validation failed: fixing errors (Attempt {retry_count}/{max_retries})")

                correction_prompt = prompt_builder.build_correction(
                    invalid_yaml=cleaned_yaml,
                    errors=errors,
                    platform=detected_platform,
                    analysis=analysis
                )

                raw_yaml_output = await llm_client.generate(correction_prompt)
                cleaned_yaml = strip_markdown_fences(raw_yaml_output)

                is_valid, errors = validator.validate(detected_platform, cleaned_yaml, services_needed=analysis.services_needed)


            if is_valid:
                await _report("validating", "Validation passed successfully")
            else:
                await _report("validating", f"Validation found {len(errors)} issue(s)")

            return PipelineResult.from_analysis(
                analysis=analysis,
                platform=detected_platform,
                yaml_output=cleaned_yaml,
                validation_passed=is_valid,
                validation_errors=errors,
            )
        finally:
            await llm_client.close()


    except CloneError:
        raise

    except Exception as e:
        logger.exception("Pipeline execution failed")
        raise RuntimeError(f"Pipeline failed: {e}") from e

    finally:
        if workspace and workspace.exists():
            logger.info("Cleaning up workspace %s", workspace)
            shutil.rmtree(workspace, ignore_errors=True)
