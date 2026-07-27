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
                install_command="pip install -r requirements.txt",
            ),
            "requirements.txt": DependencyInfo(
                manager="pip", language="python",
                install_command="pip install -r requirements.txt",
            ),
            "Pipfile": DependencyInfo(
                manager="pipenv", language="python",
                install_command="pipenv install",
            ),
            "poetry.lock": DependencyInfo(
                manager="poetry", language="python",
                install_command="poetry install",
            ),
            "uv.lock": DependencyInfo(
                manager="uv", language="python",
                install_command="uv sync",
            ),
            "setup.py": DependencyInfo(
                manager="pip", language="python",
                install_command="pip install -r requirements.txt",
            ),
        }

    @property
    def test_configs(self) -> dict[str, TestInfo]:
        return {
            "pytest.ini": TestInfo(framework="pytest", command="pytest"),
            "setup.cfg": TestInfo(framework="pytest", command="pytest"),
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
                    return TestInfo(framework="pytest", command="pytest")
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
