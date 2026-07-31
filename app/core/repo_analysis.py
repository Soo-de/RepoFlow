import logging
import subprocess
from pathlib import Path
from dataclasses import dataclass, field

from app.core.detectors import default_registry, DetectorRegistry

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", ".tox", ".mypy_cache",
    ".pytest_cache", "vendor", "target", ".next", ".nuxt",
}

CI_CONFIG_PATHS = [
    ".github/workflows",
    "azure-pipelines.yml",
    ".azure-pipelines",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    ".circleci/config.yml",
    ".travis.yml",
    "bitbucket-pipelines.yml",
]


@dataclass
class RepoAnalysis:
    primary_language: str = "unknown"
    languages: dict[str, int] = field(default_factory=dict)
    runtime_version: str | None = None
    dependency_manager: str = "unknown"
    manifest_file: str | None = None
    lockfile: str | None = None
    working_dir: str | None = None
    cache_path: str = "$(Pipeline.Workspace)/.cache"
    cache_env_var: str | None = None
    azure_setup_task: str = "UsePythonVersion@0"
    azure_version_key: str = "versionSpec"
    github_setup_action: str = "actions/setup-python@v5"
    github_version_key: str = "python-version"
    install_command: str = ""
    build_command: str | None = None
    publish_command: str | None = None
    test_framework: str | None = None
    test_command: str | None = None
    has_dockerfile: bool = False
    dockerfile_content: str | None = None
    dockerfile_path: str | None = None
    services_needed: list[str] = field(default_factory=list)
    monorepo: bool = False
    existing_pipeline_files: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    default_branch: str = "main"
    image_name: str = ""


def analyze(repo_dir: Path, registry: DetectorRegistry | None = None) -> RepoAnalysis:
    """Walk the cloned repository and build a RepoAnalysis profile.

    Uses the detector registry to delegate language-specific detection
    to individual ecosystem plugins instead of hardcoded dictionaries.
    """
    reg = registry or default_registry
    result = RepoAnalysis()

    _scan_languages(repo_dir, result, reg)
    _detect_dependency_manager(repo_dir, result, reg)
    _detect_test_framework(repo_dir, result, reg)
    _detect_services(repo_dir, result, reg)
    _detect_dockerfile(repo_dir, result)
    _detect_ci_configs(repo_dir, result)
    _detect_entry_points(repo_dir, result, reg)
    _detect_runtime_version(repo_dir, result, reg)
    _detect_monorepo(repo_dir, result, reg)
    _detect_default_branch(repo_dir, result)

    logger.info(
        "Analysis complete: language=%s, dep_manager=%s, manifest=%s, working_dir=%s, test=%s",
        result.primary_language, result.dependency_manager, result.manifest_file, result.working_dir, result.test_framework,
    )
    return result


def _scan_languages(repo_dir: Path, result: RepoAnalysis, registry: DetectorRegistry) -> None:
    """Count source files by language extension using the registry's extension map."""
    extension_map = registry.extension_map
    counts: dict[str, int] = {}

    for path in repo_dir.rglob("*"):
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if not path.is_file():
            continue

        lang = extension_map.get(path.suffix.lower())
        if lang:
            counts[lang] = counts.get(lang, 0) + 1

    result.languages = dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    if counts:
        result.primary_language = max(counts, key=counts.get)
    else:
        result.primary_language = "unknown"


def _detect_dependency_manager(
    repo_dir: Path, result: RepoAnalysis, registry: DetectorRegistry,
) -> None:
    """Identify package manager by querying each detector's dependency markers."""
    # Check root level first, then immediate subdirectories
    for search_dir in _search_dirs(repo_dir):
        for detector in registry.detectors:
            # First check custom detector method (e.g. C# .csproj / .sln rglob)
            custom_info = detector.detect_dependency_info(search_dir)
            if custom_info:
                result.dependency_manager = custom_info.manager
                result.manifest_file = custom_info.manifest_file
                result.lockfile = custom_info.lockfile
                # Set working_dir if defined or if search_dir is a subdirectory
                if custom_info.working_dir:
                    result.working_dir = custom_info.working_dir
                elif search_dir != repo_dir:
                    result.working_dir = search_dir.relative_to(repo_dir).as_posix()
                else:
                    result.working_dir = None

                if result.working_dir and custom_info.lockfile and not ("/" in custom_info.lockfile):
                    result.lockfile = f"{result.working_dir}/{custom_info.lockfile}"

                result.cache_path = custom_info.cache_path
                result.cache_env_var = custom_info.cache_env_var
                result.azure_setup_task = custom_info.azure_setup_task
                result.azure_version_key = custom_info.azure_version_key
                result.github_setup_action = custom_info.github_setup_action
                result.github_version_key = custom_info.github_version_key
                result.install_command = custom_info.install_command
                result.build_command = custom_info.build_command
                result.publish_command = custom_info.publish_command
                if result.primary_language == "unknown":
                    result.primary_language = custom_info.language
                return

            # Then check exact marker files
            for marker_file, dep_info in detector.dependency_markers.items():
                if (search_dir / marker_file).exists():
                    resolved = detector.resolve_dependency_info(search_dir, marker_file, dep_info)
                    result.dependency_manager = resolved.manager

                    # Calculate working_dir for subfolders if not explicitly set
                    if resolved.working_dir:
                        result.working_dir = resolved.working_dir
                    elif search_dir != repo_dir:
                        result.working_dir = search_dir.relative_to(repo_dir).as_posix()
                    else:
                        result.working_dir = None

                    # Format manifest_file with working_dir prefix if nested
                    if result.working_dir and not (resolved.manifest_file and "/" in resolved.manifest_file):
                        result.manifest_file = f"{result.working_dir}/{resolved.manifest_file or marker_file}"
                    else:
                        result.manifest_file = resolved.manifest_file or marker_file

                    # Format lockfile with working_dir prefix if nested
                    if resolved.lockfile:
                        if result.working_dir and not ("/" in resolved.lockfile):
                            result.lockfile = f"{result.working_dir}/{resolved.lockfile}"
                        else:
                            result.lockfile = resolved.lockfile
                    else:
                        result.lockfile = None

                    result.cache_path = resolved.cache_path
                    result.cache_env_var = resolved.cache_env_var
                    result.azure_setup_task = resolved.azure_setup_task
                    result.azure_version_key = resolved.azure_version_key
                    result.github_setup_action = resolved.github_setup_action
                    result.github_version_key = resolved.github_version_key
                    result.install_command = resolved.install_command
                    result.build_command = resolved.build_command
                    result.publish_command = resolved.publish_command
                    if result.primary_language == "unknown":
                        result.primary_language = resolved.language
                    return

    result.dependency_manager = "unknown"


def _detect_test_framework(
    repo_dir: Path, result: RepoAnalysis, registry: DetectorRegistry,
) -> None:
    """Detect test framework by delegating to each detector's custom logic."""
    for search_dir in _search_dirs(repo_dir):
        for detector in registry.detectors:
            test_info = detector.detect_test_framework(search_dir)
            if test_info:
                result.test_framework = test_info.framework
                result.test_command = test_info.command
                return

    # Language-based built-in test defaults (Go and Rust have no config files)
    for detector in registry.detectors:
        if detector.language == result.primary_language and hasattr(detector, "default_test_info"):
            default = detector.default_test_info()
            result.test_framework = default.framework
            result.test_command = default.command
            return


def _detect_services(
    repo_dir: Path, result: RepoAnalysis, registry: DetectorRegistry,
) -> None:
    """Scan dependency files for known service client library references."""
    services: set[str] = set()

    for search_dir in _search_dirs(repo_dir):
        for detector in registry.detectors:
            for dep_file in detector.dep_files_for_service_scan:
                path = search_dir / dep_file
                if not path.exists():
                    continue
                try:
                    content = path.read_text(encoding="utf-8").lower()
                    for hint in detector.service_hints:
                        if hint.library.lower() in content:
                            services.add(hint.service)
                except OSError:
                    continue

    result.services_needed = sorted(services)


COMMON_DOCKERFILE_PATHS = [
    "Dockerfile",
    "dockerfile",
    "Dockerfile.dev",
    "Dockerfile.prod",
    "docker/Dockerfile",
    "docker/dockerfile",
    ".docker/Dockerfile",
]


def _detect_dockerfile(repo_dir: Path, result: RepoAnalysis) -> None:
    """Detect Dockerfile location in repository (case-insensitive and subfolder aware)."""
    for relative_path in COMMON_DOCKERFILE_PATHS:
        full_path = repo_dir / relative_path
        if full_path.is_file():
            result.has_dockerfile = True
            result.dockerfile_path = relative_path
            return

    # Search for any file named Dockerfile or dockerfile (ignoring skip dirs)
    for candidate in repo_dir.rglob("*"):
        if any(skip in candidate.parts for skip in SKIP_DIRS):
            continue
        if candidate.is_file() and candidate.name.lower() == "dockerfile":
            result.has_dockerfile = True
            result.dockerfile_path = candidate.relative_to(repo_dir).as_posix()
            return


def _detect_ci_configs(repo_dir: Path, result: RepoAnalysis) -> None:
    """Find existing CI/CD configuration files."""
    found: list[str] = []

    for ci_path in CI_CONFIG_PATHS:
        full = repo_dir / ci_path
        if full.is_dir():
            for f in full.iterdir():
                if f.is_file() and f.suffix in (".yml", ".yaml"):
                    found.append((Path(ci_path) / f.name).as_posix())
        elif full.is_file():
            found.append(ci_path)

    result.existing_pipeline_files = found


def _detect_entry_points(
    repo_dir: Path, result: RepoAnalysis, registry: DetectorRegistry,
) -> None:
    """Find common entry point files using patterns from all detectors."""
    found: list[str] = []

    for pattern in registry.all_entry_point_patterns():
        for match in repo_dir.rglob(pattern):
            if any(skip in match.parts for skip in SKIP_DIRS):
                continue
            rel = match.relative_to(repo_dir).as_posix()
            found.append(rel)

    # Go-specific: check cmd/ directory for sub-commands
    if result.primary_language == "go":
        cmd_dir = repo_dir / "cmd"
        if cmd_dir.is_dir():
            for sub in cmd_dir.iterdir():
                if sub.is_dir():
                    found.append(f"cmd/{sub.name}/")

    result.entry_points = found


def _detect_runtime_version(
    repo_dir: Path, result: RepoAnalysis, registry: DetectorRegistry,
) -> None:
    """Delegate runtime version detection to the matching detector."""
    for detector in registry.detectors:
        if detector.language == result.primary_language:
            version = detector.detect_runtime_version(repo_dir)
            if version:
                result.runtime_version = version
                return

    # Fallback: try all detectors in case language wasn't matched
    for detector in registry.detectors:
        version = detector.detect_runtime_version(repo_dir)
        if version:
            result.runtime_version = version
            return


def _detect_monorepo(
    repo_dir: Path, result: RepoAnalysis, registry: DetectorRegistry,
) -> None:
    """Heuristic: multiple package manager files in subdirectories = monorepo."""
    markers = registry.all_monorepo_markers()
    sub_packages = 0

    for child in repo_dir.iterdir():
        if child.is_dir() and child.name not in SKIP_DIRS:
            for marker in markers:
                if (child / marker).exists():
                    sub_packages += 1
                    break

    result.monorepo = sub_packages >= 2


def _search_dirs(repo_dir: Path) -> list[Path]:
    """Return the root directory followed by its immediate non-skipped subdirectories.

    This ordering ensures root-level markers take priority over nested ones.
    """
    dirs = [repo_dir]
    for child in sorted(repo_dir.iterdir()):
        if child.is_dir() and child.name not in SKIP_DIRS:
            dirs.append(child)
    return dirs


def _detect_default_branch(repo_dir: Path, result: RepoAnalysis) -> None:
    """Detect the repository's default branch from the cloned checkout.

    After git clone, HEAD points to the default branch. We read it
    with rev-parse so the generated pipeline triggers on the real branch
    rather than hardcoding main/master.
    """
    try:
        output = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=repo_dir, timeout=5,
        )
        branch = output.stdout.strip()
        if branch and output.returncode == 0:
            result.default_branch = branch
    except (subprocess.TimeoutExpired, OSError):
        logger.debug("Could not detect default branch, using fallback 'main'")
