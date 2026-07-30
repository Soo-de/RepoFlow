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


def read_dockerfile(repo_dir: Path) -> str:
    """Read and return the content of an existing Dockerfile."""
    dockerfile_path = repo_dir / DOCKERFILE_NAME
    return dockerfile_path.read_text(encoding="utf-8")


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
    """Orchestrate Dockerfile resolution: read existing or generate new."""
    image_name = extract_repo_name(repo_url)

    if analysis.has_dockerfile:
        logger.info("Existing Dockerfile found, reading content")
        content = read_dockerfile(repo_dir)
        return DockerContext(
            dockerfile_content=content,
            image_name=image_name,
            was_generated=False,
        )

    logger.info("No Dockerfile found, generating via LLM")
    content = await generate_dockerfile(llm_client, analysis)
    return DockerContext(
        dockerfile_content=content,
        image_name=image_name,
        was_generated=True,
    )
