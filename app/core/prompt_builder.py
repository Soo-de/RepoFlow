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

    def build_correction(
        self,
        invalid_yaml: str,
        errors: list[str],
        platform: Platform | None = None,
        analysis: RepoAnalysis | None = None,
    ) -> str:
        """Render the correction prompt template with validation errors, invalid YAML, and optional project context."""
        try:
            template = self._env.get_template("correction.j2")
        except jinja2.TemplateNotFound as err:
            raise ValueError("Correction prompt template 'correction.j2' not found.") from err

        platform_name = platform.value if platform else "CI/CD"
        return template.render(
            invalid_yaml=invalid_yaml,
            validation_errors=errors,
            platform_name=platform_name,
            analysis=analysis,
        )


