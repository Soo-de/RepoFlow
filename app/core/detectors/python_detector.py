from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, PlatformSetupInfo, TestInfo, ServiceHint
from app.core.platform_detect import Platform


class PythonDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "python"

    @property
    def platform_setups(self) -> dict[Platform, PlatformSetupInfo]:
        return {
            Platform.GITHUB_ACTIONS: PlatformSetupInfo("actions/setup-python@v5", "python-version"),
            Platform.AZURE_PIPELINES: PlatformSetupInfo("UsePythonVersion@0", "versionSpec"),
        }

    @property
    def extension_map(self) -> dict[str, str]:
        return {".py": "python"}

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "pyproject.toml": DependencyInfo(
                manager="pip", language="python",
                install_command="pip install -e .",
                manifest_file="pyproject.toml",
                cache_path="$(Pipeline.Workspace)/.pip",
                cache_env_var="PIP_CACHE_DIR",
            ),
            "requirements.txt": DependencyInfo(
                manager="pip", language="python",
                install_command="pip install -r requirements.txt",
                manifest_file="requirements.txt",
                cache_path="$(Pipeline.Workspace)/.pip",
                cache_env_var="PIP_CACHE_DIR",
            ),
            "Pipfile": DependencyInfo(
                manager="pipenv", language="python",
                install_command="pipenv install",
                manifest_file="Pipfile",
                cache_path="$(Pipeline.Workspace)/.pip",
                cache_env_var="PIP_CACHE_DIR",
            ),
            "poetry.lock": DependencyInfo(
                manager="poetry", language="python",
                install_command="poetry install",
                manifest_file="pyproject.toml",
                lockfile="poetry.lock",
                cache_path="$(Pipeline.Workspace)/.cache/pypoetry",
            ),
            "uv.lock": DependencyInfo(
                manager="uv", language="python",
                install_command="uv sync",
                manifest_file="pyproject.toml",
                lockfile="uv.lock",
                cache_path="$(Pipeline.Workspace)/.cache/uv",
                cache_env_var="UV_CACHE_DIR",
            ),
            "setup.py": DependencyInfo(
                manager="pip", language="python",
                install_command="pip install -e .",
                manifest_file="setup.py",
                cache_path="$(Pipeline.Workspace)/.pip",
                cache_env_var="PIP_CACHE_DIR",
            ),
        }

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        """Adjust install command based on which files actually coexist.

        When pyproject.toml or setup.py is matched but requirements.txt
        also exists, prefer requirements.txt for reproducible CI builds.
        Checks for optional dev dependencies (e.g., [project.optional-dependencies] dev)
        to ensure test tools like pytest get installed.
        """
        install_cmd = base_info.install_command
        manifest = base_info.manifest_file or matched_marker
        lockfile = base_info.lockfile

        if matched_marker in ("pyproject.toml", "setup.py"):
            req_file = directory / "requirements.txt"
            if req_file.exists():
                install_cmd = "pip install -r requirements.txt"
                manifest = "requirements.txt"
                lockfile = "requirements.txt"
            elif (directory / "poetry.lock").exists():
                lockfile = "poetry.lock"
            elif (directory / "uv.lock").exists():
                lockfile = "uv.lock"
            else:
                pyproject = directory / "pyproject.toml"
                if pyproject.exists():
                    try:
                        content = pyproject.read_text(encoding="utf-8")
                        if "[project.optional-dependencies]" in content or "[tool.poetry.group.dev]" in content:
                            install_cmd = "pip install -e .[dev]"
                    except OSError:
                        pass
        elif matched_marker == "requirements.txt":
            lockfile = "requirements.txt"
            if (directory / "requirements-dev.txt").exists():
                install_cmd = "pip install -r requirements.txt -r requirements-dev.txt"
            elif (directory / "requirements_dev.txt").exists():
                install_cmd = "pip install -r requirements.txt -r requirements_dev.txt"

        is_static_site = (directory / "mkdocs.yml").exists() or (directory / "pelicanconf.py").exists()
        if is_static_site:
            app_type = "static_frontend"
            publish_dir = "site"
            runner_image = "nginx:alpine"
            runner_entrypoint = 'nginx -g "daemon off;"'
        else:
            app_type = "runtime_service"
            publish_dir = None
            runner_image = "python:3.12-slim"
            runner_entrypoint = "python main.py"

        return DependencyInfo(
            manager=base_info.manager,
            language=base_info.language,
            install_command=install_cmd,
            build_command=base_info.build_command,
            publish_command=base_info.publish_command,
            manifest_file=manifest,
            lockfile=lockfile,
            cache_path=base_info.cache_path,
            cache_env_var=base_info.cache_env_var,
            runner_image=runner_image,
            runner_entrypoint=runner_entrypoint,
            app_type=app_type,
            publish_dir=publish_dir,
        )

    @property
    def test_configs(self) -> dict[str, TestInfo]:
        return {
            "pytest.ini": TestInfo(framework="pytest", command="python -m pytest"),
            "setup.cfg": TestInfo(framework="pytest", command="python -m pytest"),
            "tox.ini": TestInfo(framework="tox", command="tox"),
        }

    @property
    def service_hints(self) -> list[ServiceHint]:
        return [
            ServiceHint("psycopg2", "postgres"),
            ServiceHint("psycopg", "postgres"),
            ServiceHint("asyncpg", "postgres"),
            ServiceHint("pymysql", "mysql"),
            ServiceHint("redis", "redis"),
            ServiceHint("pymongo", "mongodb"),
            ServiceHint("celery", "redis"),
            ServiceHint("elasticsearch", "elasticsearch"),
            ServiceHint("rabbitmq", "rabbitmq"),
        ]

    @property
    def dep_files_for_service_scan(self) -> list[str]:
        return ["requirements.txt", "Pipfile"]

    @property
    def runtime_version_files(self) -> dict[str, str]:
        return {".python-version": "python"}

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["main.py", "app.py", "manage.py", "wsgi.py", "asgi.py"]

    @property
    def monorepo_markers(self) -> list[str]:
        return ["pyproject.toml"]

    def detect_test_framework(self, directory: Path) -> TestInfo | None:
        # Check dedicated config files first
        result = super().detect_test_framework(directory)
        if result:
            return result

        # Check for tests/ or test/ directories
        if (directory / "tests").is_dir():
            return TestInfo(framework="pytest", command="python -m pytest tests")
        if (directory / "test").is_dir():
            return TestInfo(framework="pytest", command="python -m pytest test")

        # Fall back to parsing pyproject.toml for pytest references
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "pytest" in content or "unittest" in content:
                    return TestInfo(framework="pytest", command="python -m pytest")
            except OSError:
                pass

        # Check for test_*.py or *_test.py files
        for pattern in ("test_*.py", "*_test.py"):
            for match in directory.rglob(pattern):
                if not any(skip in match.parts for skip in ("SKIP_DIRS", ".git", "node_modules", ".venv", "venv")):
                    return TestInfo(framework="pytest", command="python -m pytest")

        return None

    def detect_runtime_version(self, repo_dir: Path) -> str | None:
        import re

        # 1. Check .python-version file first
        result = super().detect_runtime_version(repo_dir)
        if result:
            return result.strip()

        # 2. Check runtime.txt (e.g. python-3.11.4 -> 3.11)
        runtime_txt = repo_dir / "runtime.txt"
        if runtime_txt.exists():
            try:
                content = runtime_txt.read_text(encoding="utf-8").strip()
                match = re.search(r"(\d+\.\d+)", content)
                if match:
                    return match.group(1)
            except OSError:
                pass

        # 3. Check pyproject.toml
        pyproject = repo_dir / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if "requires-python" in line and "=" in line:
                        match = re.search(r"(\d+\.\d+)", line)
                        if match:
                            return match.group(1)
            except OSError:
                pass

        # 4. Check Pipfile
        pipfile = repo_dir / "Pipfile"
        if pipfile.exists():
            try:
                content = pipfile.read_text(encoding="utf-8")
                match = re.search(r'python_version\s*=\s*["\'](\d+\.\d+)["\']', content)
                if match:
                    return match.group(1)
            except OSError:
                pass

        return None
