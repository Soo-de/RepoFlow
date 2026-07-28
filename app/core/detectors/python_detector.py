from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, TestInfo, ServiceHint


class PythonDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "python"

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
                manifest_file="poetry.lock",
                cache_path="$(Pipeline.Workspace)/.cache/pypoetry",
            ),
            "uv.lock": DependencyInfo(
                manager="uv", language="python",
                install_command="uv sync",
                manifest_file="uv.lock",
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

        if matched_marker in ("pyproject.toml", "setup.py"):
            req_file = directory / "requirements.txt"
            if req_file.exists():
                install_cmd = "pip install -r requirements.txt"
                manifest = "requirements.txt"
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
            if (directory / "requirements-dev.txt").exists():
                install_cmd = "pip install -r requirements.txt -r requirements-dev.txt"
            elif (directory / "requirements_dev.txt").exists():
                install_cmd = "pip install -r requirements.txt -r requirements_dev.txt"

        return DependencyInfo(
            manager=base_info.manager,
            language=base_info.language,
            install_command=install_cmd,
            build_command=base_info.build_command,
            manifest_file=manifest,
            cache_path=base_info.cache_path,
            cache_env_var=base_info.cache_env_var,
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

        # Fall back to parsing pyproject.toml for pytest references
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                if "pytest" in content:
                    return TestInfo(framework="pytest", command="python -m pytest")
            except OSError:
                pass

        return None

    def detect_runtime_version(self, repo_dir: Path) -> str | None:
        # Check .python-version file first
        result = super().detect_runtime_version(repo_dir)
        if result:
            return result

        # Fall back to parsing requires-python from pyproject.toml
        pyproject = repo_dir / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if "requires-python" in line and "=" in line:
                        version = line.split("=", 1)[1].strip().strip('"').strip("'")
                        return version
            except OSError:
                pass

        return None
