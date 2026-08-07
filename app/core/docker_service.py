import logging
from dataclasses import dataclass
from pathlib import Path

from app.core.repo_analysis import RepoAnalysis
from app.core.prompt_builder import PromptBuilder
from app.core.validation import strip_markdown_fences

logger = logging.getLogger(__name__)

DOCKERFILE_NAME = "Dockerfile"


@dataclass
class DockerContext:
    """Holds Dockerfile content and derived image metadata."""
    dockerfile_content: str
    image_name: str
    was_generated: bool


def extract_repo_name(repo_url: str) -> str:
    """Derive a Docker-friendly image name from a repository URL."""
    name = repo_url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name.lower()


def read_dockerfile(repo_dir: Path, custom_path: str | None = None) -> str:
    """Read and return the content of an existing Dockerfile."""
    target_rel = custom_path or DOCKERFILE_NAME
    dockerfile_path = repo_dir / target_rel
    return dockerfile_path.read_text(encoding="utf-8").strip()


def is_placeholder_dockerfile(content: str) -> bool:
    """Check if Dockerfile content is empty or lacks a valid FROM directive."""
    stripped = content.strip()
    if not stripped:
        return True
    # If "FROM " exists anywhere in the file (case-insensitive), it is a valid Dockerfile
    return "FROM " not in stripped.upper()


async def generate_dockerfile(llm_client, analysis: RepoAnalysis) -> str:
    """Use the LLM to generate a multi-stage Dockerfile based on project analysis."""
    prompt_builder = PromptBuilder()
    prompt = prompt_builder.build_dockerfile(analysis)

    logger.info("Generating Dockerfile via LLM for %s project", analysis.primary_language)
    raw_output = await llm_client.generate(prompt)
    return strip_markdown_fences(raw_output)


async def build_docker_context(
    repo_dir: Path,
    analysis: RepoAnalysis,
    llm_client,
    repo_url: str,
) -> DockerContext:
    """Orchestrate Dockerfile resolution: read valid existing Dockerfile or generate new via LLM."""
    image_name = extract_repo_name(repo_url)

    if analysis.has_dockerfile:
        try:
            content = read_dockerfile(repo_dir, getattr(analysis, "dockerfile_path", None))
            if not is_placeholder_dockerfile(content):
                logger.info("Valid existing Dockerfile found, reading content directly")
                return DockerContext(
                    dockerfile_content=content,
                    image_name=image_name,
                    was_generated=False,
                )
            logger.warning("Existing Dockerfile is a placeholder or stub. Generating production Dockerfile via LLM.")
        except (OSError, UnicodeDecodeError) as err:
            logger.warning("Failed reading existing Dockerfile (%s). Generating via LLM.", err)

    logger.info("Generating Dockerfile via LLM")
    content = await generate_dockerfile(llm_client, analysis)
    return DockerContext(
        dockerfile_content=content,
        image_name=image_name,
        was_generated=True,
    )
