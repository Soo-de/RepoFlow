import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", ".tox", ".mypy_cache",
    ".pytest_cache", "vendor", "target", ".next", ".nuxt",
}

DEPENDENCY_MARKERS: dict[str, tuple[str, str]] = {
    "pyproject.toml": ("python", "pip"),
    "requirements.txt": ("python", "pip"),
    "Pipfile": ("python", "pipenv"),
    "poetry.lock": ("python", "poetry"),
    "uv.lock": ("python", "uv"),
    "setup.py": ("python", "pip"),
    "package.json": ("javascript", "npm"),
    "yarn.lock": ("javascript", "yarn"),
    "pnpm-lock.yaml": ("javascript", "pnpm"),
    "go.mod": ("go", "go_modules"),
    "Cargo.toml": ("rust", "cargo"),
    "pom.xml": ("java", "maven"),
    "build.gradle": ("java", "gradle"),
    "build.gradle.kts": ("kotlin", "gradle"),
    "Gemfile": ("ruby", "bundler"),
    "composer.json": ("php", "composer"),
    "Package.swift": ("swift", "spm"),
}

INSTALL_COMMANDS: dict[str, str] = {
    "pip": "pip install -r requirements.txt",
    "poetry": "poetry install",
    "pipenv": "pipenv install",
    "uv": "uv sync",
    "npm": "npm ci",
    "yarn": "yarn install --frozen-lockfile",
    "pnpm": "pnpm install --frozen-lockfile",
    "go_modules": "go mod download",
    "cargo": "cargo build",
    "maven": "mvn install",
    "gradle": "gradle build",
    "bundler": "bundle install",
    "composer": "composer install",
    "spm": "swift package resolve",
}

BUILD_COMMANDS: dict[str, str] = {
    "npm": "npm run build",
    "yarn": "yarn build",
    "pnpm": "pnpm build",
    "cargo": "cargo build --release",
    "maven": "mvn package",
    "gradle": "gradle build",
    "go_modules": "go build ./...",
}

TEST_FRAMEWORKS: dict[str, tuple[str, str]] = {
    "pytest.ini": ("pytest", "pytest"),
    "setup.cfg": ("pytest", "pytest"),
    "tox.ini": ("tox", "tox"),
    "jest.config.js": ("jest", "npx jest"),
    "jest.config.ts": ("jest", "npx jest"),
    "vitest.config.ts": ("vitest", "npx vitest run"),
    "vitest.config.js": ("vitest", "npx vitest run"),
    ".rspec": ("rspec", "bundle exec rspec"),
    "phpunit.xml": ("phpunit", "vendor/bin/phpunit"),
}

SERVICE_HINTS: dict[str, str] = {
    "psycopg2": "postgres",
    "psycopg": "postgres",
    "asyncpg": "postgres",
    "pg": "postgres",
    "mysql2": "mysql",
    "pymysql": "mysql",
    "redis": "redis",
    "ioredis": "redis",
    "mongodb": "mongodb",
    "pymongo": "mongodb",
    "mongoose": "mongodb",
    "elasticsearch": "elasticsearch",
    "rabbitmq": "rabbitmq",
    "amqplib": "rabbitmq",
    "celery": "redis",
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

ENTRY_POINT_PATTERNS = [
    "main.py", "app.py", "manage.py", "wsgi.py", "asgi.py",
    "index.js", "index.ts", "server.js", "server.ts", "app.js", "app.ts",
    "main.go", "main.rs", "Main.java", "Program.cs",
]


@dataclass
class RepoAnalysis:
    primary_language: str = "unknown"
    languages: dict[str, int] = field(default_factory=dict)
    runtime_version: str | None = None
    dependency_manager: str = "unknown"
    install_command: str = ""
    build_command: str | None = None
    test_framework: str | None = None
    test_command: str | None = None
    has_dockerfile: bool = False
    services_needed: list[str] = field(default_factory=list)
    monorepo: bool = False
    existing_pipeline_files: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)


def analyze(repo_dir: Path) -> RepoAnalysis:
    """Walk the cloned repository and build a RepoAnalysis profile."""
    result = RepoAnalysis()

    _scan_languages(repo_dir, result)
    _detect_dependency_manager(repo_dir, result)
    _detect_test_framework(repo_dir, result)
    _detect_services(repo_dir, result)
    _detect_dockerfile(repo_dir, result)
    _detect_ci_configs(repo_dir, result)
    _detect_entry_points(repo_dir, result)
    _detect_runtime_version(repo_dir, result)
    _detect_monorepo(repo_dir, result)

    logger.info(
        "Analysis complete: language=%s, dep_manager=%s, test=%s",
        result.primary_language, result.dependency_manager, result.test_framework,
    )
    return result


def _scan_languages(repo_dir: Path, result: RepoAnalysis) -> None:
    """Count source files by language extension."""
    counts: dict[str, int] = {}

    for path in repo_dir.rglob("*"):
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        if not path.is_file():
            continue

        lang = LANGUAGE_EXTENSIONS.get(path.suffix.lower())
        if lang:
            counts[lang] = counts.get(lang, 0) + 1

    result.languages = dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    if counts:
        result.primary_language = max(counts, key=counts.get)
    else:
        result.primary_language = "unknown"


def _detect_dependency_manager(repo_dir: Path, result: RepoAnalysis) -> None:
    """Identify package manager from marker files (root first, then one level deep)."""
    # Check root level first
    match = _find_dependency_marker(repo_dir)
    if match:
        result.dependency_manager = match[0]
        result.install_command = match[1]
        result.build_command = match[2]
        if result.primary_language == "unknown":
            result.primary_language = match[3]
        return

    # Fallback: check immediate subdirectories
    for child in sorted(repo_dir.iterdir()):
        if child.is_dir() and child.name not in SKIP_DIRS:
            match = _find_dependency_marker(child)
            if match:
                result.dependency_manager = match[0]
                result.install_command = match[1]
                result.build_command = match[2]
                if result.primary_language == "unknown":
                    result.primary_language = match[3]
                return

    result.dependency_manager = "unknown"


def _find_dependency_marker(directory: Path) -> tuple[str, str, str | None, str] | None:
    """Check a directory for dependency marker files.

    Returns (manager, install_cmd, build_cmd, language) or None.
    """
    for marker, (lang, manager) in DEPENDENCY_MARKERS.items():
        if (directory / marker).exists():
            return (
                manager,
                INSTALL_COMMANDS.get(manager, ""),
                BUILD_COMMANDS.get(manager),
                lang,
            )
    return None


def _detect_test_framework(repo_dir: Path, result: RepoAnalysis) -> None:
    """Detect test framework from config files (root first, then one level deep)."""
    if _check_test_framework_in_dir(repo_dir, result):
        return

    for child in sorted(repo_dir.iterdir()):
        if child.is_dir() and child.name not in SKIP_DIRS:
            if _check_test_framework_in_dir(child, result):
                return

    # Language-based defaults
    if result.primary_language == "go":
        result.test_framework = "go_test"
        result.test_command = "go test ./..."
    elif result.primary_language == "rust":
        result.test_framework = "cargo_test"
        result.test_command = "cargo test"


def _check_test_framework_in_dir(directory: Path, result: RepoAnalysis) -> bool:
    """Check a single directory for test framework markers. Returns True if found."""
    for config_file, (framework, command) in TEST_FRAMEWORKS.items():
        if (directory / config_file).exists():
            result.test_framework = framework
            result.test_command = command
            return True

    if (directory / "pyproject.toml").exists():
        try:
            content = (directory / "pyproject.toml").read_text(encoding="utf-8")
            if "pytest" in content:
                result.test_framework = "pytest"
                result.test_command = "pytest"
                return True
        except OSError:
            pass

    if (directory / "package.json").exists():
        try:
            content = (directory / "package.json").read_text(encoding="utf-8")
            if '"test"' in content:
                result.test_command = "npm test"
                if "jest" in content:
                    result.test_framework = "jest"
                elif "vitest" in content:
                    result.test_framework = "vitest"
                elif "mocha" in content:
                    result.test_framework = "mocha"
                return True
        except OSError:
            pass

    return False


def _detect_services(repo_dir: Path, result: RepoAnalysis) -> None:
    """Heuristic: scan dependency files for known service client libraries."""
    services: set[str] = set()
    dep_files = ["requirements.txt", "Pipfile", "package.json", "Cargo.toml", "go.mod"]

    _scan_services_in_dir(repo_dir, dep_files, services)

    for child in sorted(repo_dir.iterdir()):
        if child.is_dir() and child.name not in SKIP_DIRS:
            _scan_services_in_dir(child, dep_files, services)

    result.services_needed = sorted(services)


def _scan_services_in_dir(directory: Path, dep_files: list[str], services: set[str]) -> None:
    """Scan a single directory's dependency files for service hints."""
    for dep_file in dep_files:
        path = directory / dep_file
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8").lower()
            for lib, service in SERVICE_HINTS.items():
                if lib.lower() in content:
                    services.add(service)
        except OSError:
            continue


def _detect_dockerfile(repo_dir: Path, result: RepoAnalysis) -> None:
    result.has_dockerfile = (repo_dir / "Dockerfile").exists()


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


def _detect_entry_points(repo_dir: Path, result: RepoAnalysis) -> None:
    """Find common entry point files."""
    found: list[str] = []

    for pattern in ENTRY_POINT_PATTERNS:
        for match in repo_dir.rglob(pattern):
            if any(skip in match.parts for skip in SKIP_DIRS):
                continue
            rel = match.relative_to(repo_dir).as_posix()
            found.append(rel)

    if result.primary_language == "go":
        cmd_dir = repo_dir / "cmd"
        if cmd_dir.is_dir():
            for sub in cmd_dir.iterdir():
                if sub.is_dir():
                    found.append(f"cmd/{sub.name}/")

    result.entry_points = found


def _detect_runtime_version(repo_dir: Path, result: RepoAnalysis) -> None:
    """Try to extract runtime version from version-pinning files."""
    version_files: dict[str, str] = {
        ".python-version": "python",
        ".nvmrc": "javascript",
        ".node-version": "javascript",
        ".ruby-version": "ruby",
        ".go-version": "go",
        "rust-toolchain.toml": "rust",
    }

    for filename, lang in version_files.items():
        path = repo_dir / filename
        if path.exists():
            try:
                version = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
                if version:
                    result.runtime_version = version
                    return
            except (OSError, IndexError):
                continue

    if (repo_dir / "pyproject.toml").exists():
        try:
            content = (repo_dir / "pyproject.toml").read_text(encoding="utf-8")
            for line in content.splitlines():
                if "requires-python" in line and "=" in line:
                    version = line.split("=", 1)[1].strip().strip('"').strip("'")
                    result.runtime_version = version
                    return
        except OSError:
            pass

    if (repo_dir / "go.mod").exists():
        try:
            content = (repo_dir / "go.mod").read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.strip().startswith("go "):
                    result.runtime_version = line.strip().split()[1]
                    return
        except (OSError, IndexError):
            pass


def _detect_monorepo(repo_dir: Path, result: RepoAnalysis) -> None:
    """Simple heuristic: multiple package manager files in subdirs = monorepo."""
    markers = {"package.json", "pyproject.toml", "go.mod", "Cargo.toml", "pom.xml"}
    sub_packages = 0

    for child in repo_dir.iterdir():
        if child.is_dir() and child.name not in SKIP_DIRS:
            for marker in markers:
                if (child / marker).exists():
                    sub_packages += 1
                    break

    result.monorepo = sub_packages >= 2
