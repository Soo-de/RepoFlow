import logging
from dataclasses import dataclass, field

from app.core.repo_analysis import RepoAnalysis

logger = logging.getLogger(__name__)


class ReadinessError(Exception):
    """Raised when pipeline generation cannot proceed due to missing critical information."""

    def __init__(self, blockers: list[str]) -> None:
        self.blockers = blockers
        summary = "; ".join(blockers)
        super().__init__(f"Pipeline generation blocked: {summary}")


@dataclass(frozen=True)
class ReadinessWarning:
    field_name: str
    message: str


@dataclass
class ReadinessResult:
    blockers: list[str] = field(default_factory=list)
    warnings: list[ReadinessWarning] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        return len(self.blockers) == 0


def _is_empty_or_unknown(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() in ("", "unknown")


def check_readiness(analysis: RepoAnalysis) -> ReadinessResult:
    """Evaluate whether the repository analysis contains enough information
    for meaningful pipeline generation.

    Returns a ReadinessResult with any blockers (fatal) and warnings (non-fatal).
    """
    result = ReadinessResult()

    # --- Critical checks (block generation) ---

    if _is_empty_or_unknown(analysis.primary_language):
        result.blockers.append(
            "Programming language could not be detected. "
            "The language is required to determine build steps, "
            "runtime setup, and dependency management."
        )

    if analysis.dependency_info is None:
        result.blockers.append(
            "No dependency manager was detected. "
            "A dependency manager is required to generate "
            "install, build, and cache steps."
        )
    else:
        if _is_empty_or_unknown(analysis.dependency_info.manager):
            result.blockers.append(
                "Dependency manager type could not be determined. "
                "The manager name is required to generate correct "
                "install and build commands."
            )

        if not analysis.dependency_info.install_command or not analysis.dependency_info.install_command.strip():
            result.blockers.append(
                "No install command could be determined for the detected "
                "dependency manager. An install command is required to "
                "generate the dependency installation step."
            )

    # --- Warning checks (continue with defaults) ---

    if analysis.runtime_version is None:
        result.warnings.append(ReadinessWarning(
            field_name="runtime_version",
            message="Runtime version not detected — will use default",
        ))

    if analysis.manifest_file is None:
        result.warnings.append(ReadinessWarning(
            field_name="manifest_file",
            message="No manifest file detected — cache configuration may be incomplete",
        ))

    if analysis.lockfile is None:
        result.warnings.append(ReadinessWarning(
            field_name="lockfile",
            message="No lock file detected — builds may not be deterministic",
        ))

    if result.blockers:
        logger.error(
            "Pipeline readiness check failed with %d blocker(s): %s",
            len(result.blockers),
            result.blockers,
        )

    if result.warnings:
        logger.info(
            "Pipeline readiness warnings: %s",
            [w.message for w in result.warnings],
        )

    return result
