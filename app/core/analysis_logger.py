"""Structured logging utility for RepoFlow repository analysis and pipeline requirements.

Provides detailed, formatted log output for repository features, dependency info,
environment requirements, platform setup, and pipeline readiness checks.
"""

import logging
from typing import Any
from app.core.repo_analysis import RepoAnalysis
from app.core.platform_detect import Platform
from app.core.readiness import ReadinessResult

logger = logging.getLogger(__name__)


def _format_val(value: Any) -> str:
    """Format None, empty, or complex values into clean readable representations."""
    if value is None:
        return "None"
    if isinstance(value, (list, tuple)):
        return repr(list(value)) if value else "[]"
    if isinstance(value, dict):
        return repr(dict(value)) if value else "{}"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return value if value else '""'
    return str(value)


def log_analysis_summary(
    analysis: RepoAnalysis,
    platform: Platform | str | None = None,
    readiness: ReadinessResult | None = None,
    log_level: int = logging.INFO,
) -> None:
    """Log every property of repository analysis, dependency info, environment requirements,
    and platform setup in a clean, visually structured key-value block.
    """
    platform_obj = Platform(platform) if isinstance(platform, str) and platform in [p.value for p in Platform] else platform
    setup = analysis.get_platform_setup(platform_obj) if isinstance(platform_obj, Platform) else None

    # Format platform setup metadata if available
    platform_setup_info = "None"
    if setup:
        extra = f", extra_inputs={setup.extra_inputs}" if setup.extra_inputs else ""
        platform_setup_info = f"task_or_action='{setup.task_or_action}', version_key='{setup.version_key}'{extra}"

    lines = [
        "",
        "================================================================================",
        "                  REPOFLOW ANALYSIS & PIPELINE REQUIREMENTS                     ",
        "================================================================================",
        " [1] REPOSITORY ANALYSIS",
        f"   • Primary Language       : {_format_val(analysis.primary_language)}",
        f"   • Language Breakdown     : {_format_val(analysis.languages)}",
        f"   • Default Branch         : {_format_val(analysis.default_branch)}",
        f"   • Is Monorepo            : {_format_val(analysis.monorepo)}",
        f"   • Entry Points           : {_format_val(analysis.entry_points)}",
        f"   • Existing CI/CD Files   : {_format_val(analysis.existing_pipeline_files)}",
        f"   • Services Needed        : {_format_val(analysis.services_needed)}",
        f"   • Has Dockerfile         : {_format_val(analysis.has_dockerfile)}",
        f"   • Dockerfile Path        : {_format_val(analysis.dockerfile_path)}",
        f"   • Docker Image Name      : {_format_val(analysis.image_name)}",
        "",
        " [2] DEPENDENCY INFO",
        f"   • Dependency Manager     : {_format_val(analysis.dependency_manager)}",
        f"   • Manifest File          : {_format_val(analysis.manifest_file)}",
        f"   • Lock File              : {_format_val(analysis.lockfile)}",
        f"   • Working Directory      : {_format_val(analysis.working_dir)}",
        f"   • Install Command        : {_format_val(analysis.install_command)}",
        f"   • Build Command          : {_format_val(analysis.build_command)}",
        f"   • Publish Command        : {_format_val(analysis.publish_command)}",
        f"   • Application Type       : {_format_val(analysis.app_type)}",
        f"   • Publish Directory      : {_format_val(analysis.publish_dir)}",
        f"   • Cache Path             : {_format_val(analysis.cache_path)}",
        f"   • Cache Env Var          : {_format_val(analysis.cache_env_var)}",
        f"   • Cache Key Files        : {_format_val(analysis.cache_key_files)}",
        "",
        " [3] ENVIRONMENT REQUIREMENTS",
        f"   • Runtime Version        : {_format_val(analysis.runtime_version)}",
        f"   • Runner Image           : {_format_val(analysis.runner_image)}",
        f"   • Runner Entrypoint      : {_format_val(analysis.runner_entrypoint)}",
        f"   • Target Platform        : {_format_val(platform_obj.value if platform_obj else None)}",
        f"   • Platform Setup Details : {platform_setup_info}",
        "",
        " [4] TEST CONFIGURATION",
        f"   • Test Framework         : {_format_val(analysis.test_framework)}",
        f"   • Test Command           : {_format_val(analysis.test_command)}",
    ]

    if readiness:
        blocker_str = f"[{', '.join(readiness.blockers)}]" if readiness.blockers else "None"
        warning_str = f"[{', '.join(w.message for w in readiness.warnings)}]" if readiness.warnings else "None"
        lines.extend([
            "",
            " [5] PIPELINE READINESS",
            f"   • Can Proceed            : {_format_val(readiness.can_proceed)}",
            f"   • Blockers               : {blocker_str}",
            f"   • Warnings               : {warning_str}",
        ])

    lines.extend([
        "================================================================================",
        "",
    ])

    logger.log(log_level, "\n".join(lines))
