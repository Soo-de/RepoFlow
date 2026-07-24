from pathlib import Path
import jinja2

from app.core.platform_detect import Platform
from app.core.repo_analysis import RepoAnalysis

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PROMPTS_DIR = BASE_DIR / "prompts"


class PromptBuilder:
    """Loads Jinja2 prompt templates and renders them with repository analysis data."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._prompts_dir = prompts_dir or DEFAULT_PROMPTS_DIR
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self._prompts_dir),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def build(self, platform: Platform, analysis: RepoAnalysis) -> str:
        """Render prompt template corresponding to the given CI/CD platform."""
        template_name = f"{platform.value}.j2"
        try:
            template = self._env.get_template(template_name)
        except jinja2.TemplateNotFound as err:
            raise ValueError(f"Prompt template for platform '{platform.value}' not found: {template_name}") from err

        return template.render(analysis=analysis)
