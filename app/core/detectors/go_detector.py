from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, TestInfo


class GoDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "go"

    @property
    def extension_map(self) -> dict[str, str]:
        return {".go": "go"}

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "go.mod": DependencyInfo(
                manager="go_modules", language="go",
                install_command="go mod download",
                build_command="go build ./...",
            ),
        }

    @property
    def test_configs(self) -> dict[str, TestInfo]:
        # Go uses built-in testing; no config file needed
        return {}

    @property
    def dep_files_for_service_scan(self) -> list[str]:
        return ["go.mod"]

    @property
    def runtime_version_files(self) -> dict[str, str]:
        return {".go-version": "go"}

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["main.go"]

    @property
    def monorepo_markers(self) -> list[str]:
        return ["go.mod"]

    def default_test_info(self) -> TestInfo:
        """Go has a built-in test runner with no config file dependency."""
        return TestInfo(framework="go_test", command="go test ./...")

    def detect_runtime_version(self, repo_dir: Path) -> str | None:
        # Check .go-version first
        result = super().detect_runtime_version(repo_dir)
        if result:
            return result

        # Fall back to parsing the go directive from go.mod
        go_mod = repo_dir / "go.mod"
        if go_mod.exists():
            try:
                content = go_mod.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if line.strip().startswith("go "):
                        return line.strip().split()[1]
            except (OSError, IndexError):
                pass

        return None
