from dataclasses import dataclass, field, asdict
from typing import Any

from app.core.repo_analysis import RepoAnalysis
from app.core.platform_detect import Platform


@dataclass(frozen=True)
class PipelineResult:
    yaml_output: str
    platform: str
    validation_passed: bool
    validation_errors: list[str]
    analysis: dict[str, Any] = field(default_factory=dict)
    dockerfile_output: str | None = None

    @staticmethod
    def from_analysis(
        analysis: RepoAnalysis,
        platform: Platform,
        yaml_output: str = "",
        validation_passed: bool = True,
        validation_errors: list[str] | None = None,
        dockerfile_output: str | None = None,
    ) -> "PipelineResult":
        return PipelineResult(
            yaml_output=yaml_output,
            platform=platform.value,
            validation_passed=validation_passed,
            validation_errors=validation_errors or [],
            analysis=asdict(analysis),
            dockerfile_output=dockerfile_output,
        )
