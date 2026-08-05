from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, PlatformSetupInfo, TestInfo
from app.core.platform_detect import Platform


class RustDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "rust"

    @property
    def platform_setups(self) -> dict[Platform, PlatformSetupInfo]:
        return {
            Platform.GITHUB_ACTIONS: PlatformSetupInfo("dtolnay/rust-toolchain@stable", "toolchain"),
        }

    @property
    def extension_map(self) -> dict[str, str]:
        return {".rs": "rust"}

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "Cargo.toml": DependencyInfo(
                manager="cargo", language="rust",
                install_command="cargo build",
                build_command="cargo build --release",
                publish_command="cargo build --release",
                manifest_file="Cargo.toml",
                lockfile="Cargo.lock",
            ),
        }

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        lockfile = "Cargo.lock" if (directory / "Cargo.lock").exists() else None
        is_wasm_site = (directory / "Trunk.toml").exists()

        if is_wasm_site:
            app_type = "static_frontend"
            publish_dir = "dist"
            runner_image = "nginx:alpine"
            runner_entrypoint = 'nginx -g "daemon off;"'
        else:
            app_type = "runtime_service"
            publish_dir = None
            runner_image = "debian:bookworm-slim"
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
            cache_key_files=[lockfile] if lockfile else ["Cargo.toml"],
        )

    @property
    def dep_files_for_service_scan(self) -> list[str]:
        return ["Cargo.toml"]

    @property
    def runtime_version_files(self) -> dict[str, str]:
        return {"rust-toolchain.toml": "rust"}

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["main.rs"]

    @property
    def monorepo_markers(self) -> list[str]:
        return ["Cargo.toml"]

    def default_test_info(self) -> TestInfo:
        """Rust has a built-in test runner with no config file dependency."""
        return TestInfo(framework="cargo_test", command="cargo test")
