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
                publish_command="go build -o /app/main .",
                manifest_file="go.mod",
                lockfile="go.sum",
                runner_image="alpine",
                runner_entrypoint="./main",
            ),
        }

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        lockfile = "go.sum" if (directory / "go.sum").exists() else None
        
        main_files = [f for f in directory.rglob("main.go") if not any(skip in f.parts for skip in (".git", "vendor", "node_modules"))]
        if main_files:
            rel_main = main_files[0].relative_to(directory).as_posix()
            if "/" in rel_main:
                pkg_dir = rel_main.rsplit("/", 1)[0]
                publish_cmd = f"go build -o /app/main ./{pkg_dir}"
            else:
                publish_cmd = "go build -o /app/main ."
        else:
            publish_cmd = base_info.publish_command

        return DependencyInfo(
            manager=base_info.manager,
            language=base_info.language,
            install_command=base_info.install_command,
            build_command=base_info.build_command,
            publish_command=publish_cmd,
            manifest_file=base_info.manifest_file or matched_marker,
            lockfile=lockfile,
            runner_image=base_info.runner_image,
            runner_entrypoint="./main",
        )

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
