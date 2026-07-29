from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, TestInfo


class CDetector(BaseDetector):
    """Detector for C and C++ ecosystems."""

    @property
    def language(self) -> str:
        return "c"

    @property
    def extension_map(self) -> dict[str, str]:
        return {
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
        }

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "CMakeLists.txt": DependencyInfo(
                manager="cmake", language="c",
                install_command="",
                build_command="cmake -B build && cmake --build build",
                manifest_file="CMakeLists.txt",
            ),
            "Makefile": DependencyInfo(
                manager="make", language="c",
                install_command="",
                build_command="make",
                manifest_file="Makefile",
            ),
            "makefile": DependencyInfo(
                manager="make", language="c",
                install_command="",
                build_command="make",
                manifest_file="makefile",
            ),
            "conanfile.txt": DependencyInfo(
                manager="conan", language="c",
                install_command="conan install . --output-folder=build --build=missing",
                build_command="cmake --build build",
                manifest_file="conanfile.txt",
            ),
            "vcpkg.json": DependencyInfo(
                manager="vcpkg", language="c",
                install_command="vcpkg install",
                build_command="cmake --build build",
                manifest_file="vcpkg.json",
            ),
            "meson.build": DependencyInfo(
                manager="meson", language="c",
                install_command="meson setup build",
                build_command="meson compile -C build",
                manifest_file="meson.build",
            ),
        }

    def detect_test_framework(self, directory: Path) -> TestInfo | None:
        """Only report test command if Makefile/CMakeLists actually defines tests."""
        makefile = directory / "Makefile"
        if not makefile.exists():
            makefile = directory / "makefile"

        if makefile.exists():
            try:
                content = makefile.read_text(encoding="utf-8").lower()
                if "test:" in content or "check:" in content or ".phony:" in content and "test" in content:
                    return TestInfo(framework="make_test", command="make test")
            except OSError:
                pass

        cmakelists = directory / "CMakeLists.txt"
        if cmakelists.exists():
            try:
                content = cmakelists.read_text(encoding="utf-8").lower()
                if "enable_testing" in content or "add_test" in content:
                    return TestInfo(framework="ctest", command="ctest --test-dir build")
            except OSError:
                pass

        return None
