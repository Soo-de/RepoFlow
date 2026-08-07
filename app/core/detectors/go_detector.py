from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, PlatformSetupInfo, TestInfo
from app.core.platform_detect import Platform


class GoDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "go"

    @property
    def default_runtime_version(self) -> str:
        return "1.22"

    @property
    def platform_setups(self) -> dict[Platform, PlatformSetupInfo]:
        return {
            Platform.GITHUB_ACTIONS: PlatformSetupInfo("actions/setup-go@v5", "go-version"),
            Platform.AZURE_PIPELINES: PlatformSetupInfo("GoTool@0", "version"),
        }

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
            ),
        }

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        lockfile = "go.sum" if (directory / "go.sum").exists() else None
        is_hugo_site = (directory / "hugo.toml").exists() or (directory / "config.toml").exists()

        if is_hugo_site:
            app_type = "static_frontend"
            publish_dir = "public"
            runner_image = "nginx:alpine"
            runner_entrypoint = 'nginx -g "daemon off;"'
        else:
            app_type = "runtime_service"
            publish_dir = None
            runner_image = "alpine"
            runner_entrypoint = "./main"

        return DependencyInfo(
            manager=base_info.manager,
            language=base_info.language,
            install_command=base_info.install_command,
            build_command=base_info.build_command,
            publish_command=base_info.publish_command,
            manifest_file=base_info.manifest_file or matched_marker,
            lockfile=lockfile,
            runner_image=runner_image,
            runner_entrypoint=runner_entrypoint,
            app_type=app_type,
            publish_dir=publish_dir,
            cache_key_files=[lockfile] if lockfile else ["go.mod"],
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

    def detect_test_framework(self, directory: Path) -> TestInfo | None:
        """Go has a built-in test runner. Only return test info if *_test.go files exist."""
        test_files = list(directory.rglob("*_test.go"))
        if test_files:
            return TestInfo(framework="go_test", command="go test ./...")
        return None

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
