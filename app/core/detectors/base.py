from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DependencyInfo:
    """Result of dependency manager detection for a single ecosystem."""
    manager: str
    language: str
    install_command: str
    build_command: str | None = None


@dataclass
class TestInfo:
    """Result of test framework detection."""
    framework: str
    command: str


@dataclass
class ServiceHint:
    """Maps a dependency library name to an infrastructure service."""
    library: str
    service: str


class BaseDetector(ABC):
    """Abstract base class that every ecosystem detector must implement.

    Each detector is responsible for a single language ecosystem (e.g. Python,
    Node.js, Go) and encapsulates all detection rules for that ecosystem:
    file extensions, dependency markers, test frameworks, service hints,
    runtime version extraction, and entry point patterns.
    """

    @property
    @abstractmethod
    def language(self) -> str:
        """Canonical lowercase language name (e.g. 'python', 'go', 'c')."""

    @property
    @abstractmethod
    def extension_map(self) -> dict[str, str]:
        """Map of file extensions to their language names.

        Allows a single detector to handle related languages, e.g.
        NodeDetector maps {".js": "javascript", ".ts": "typescript"}.
        """

    @property
    @abstractmethod
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        """Map of marker filenames to their DependencyInfo.

        Example: {"pyproject.toml": DependencyInfo(manager="pip", ...)}
        """

    @property
    def test_configs(self) -> dict[str, TestInfo]:
        """Map of test config filenames to TestInfo.

        Override in subclasses that have dedicated test config files.
        """
        return {}

    @property
    def service_hints(self) -> list[ServiceHint]:
        """Library-to-service mappings for infrastructure detection.

        Override in subclasses that reference external services.
        """
        return []

    @property
    def dep_files_for_service_scan(self) -> list[str]:
        """Filenames to scan when searching for service library references.

        Override in subclasses to list dependency manifest files.
        """
        return []

    @property
    def runtime_version_files(self) -> dict[str, str]:
        """Map of version-pinning filenames to language name.

        Example: {".python-version": "python"}
        Override in subclasses that use version pinning files.
        """
        return {}

    @property
    def entry_point_patterns(self) -> list[str]:
        """Common entry point filenames for this ecosystem.

        Example: ["main.py", "app.py", "wsgi.py"]
        """
        return []

    @property
    def monorepo_markers(self) -> list[str]:
        """Filenames whose presence in subdirectories indicates a sub-package.

        Used by the monorepo detection heuristic.
        """
        return []

    def detect_test_framework(self, directory: Path) -> TestInfo | None:
        """Detect test framework in the given directory.

        Default implementation checks self.test_configs against the directory.
        Subclasses can override for richer detection logic (e.g. parsing
        pyproject.toml or package.json contents).
        """
        for config_file, info in self.test_configs.items():
            if (directory / config_file).exists():
                return info
        return None

    def detect_runtime_version(self, repo_dir: Path) -> str | None:
        """Extract runtime version from version-pinning files.

        Default implementation reads the first line of each version file.
        Subclasses can override for custom parsing (e.g. go.mod, pyproject.toml).
        """
        for filename in self.runtime_version_files:
            path = repo_dir / filename
            if path.exists():
                try:
                    version = path.read_text(encoding="utf-8").strip().splitlines()[0].strip()
                    if version:
                        return version
                except (OSError, IndexError):
                    continue
        return None
