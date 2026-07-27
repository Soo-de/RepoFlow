from app.core.detectors.base import BaseDetector, DependencyInfo, TestInfo


class RustDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "rust"

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
            ),
        }

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
