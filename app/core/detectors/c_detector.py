from app.core.detectors.base import BaseDetector, DependencyInfo


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
                install_command="cmake -B build",
                build_command="cmake --build build",
            ),
            "Makefile": DependencyInfo(
                manager="make", language="c",
                install_command="make",
                build_command="make",
            ),
            "makefile": DependencyInfo(
                manager="make", language="c",
                install_command="make",
                build_command="make",
            ),
            "conanfile.txt": DependencyInfo(
                manager="conan", language="c",
                install_command="conan install . --output-folder=build --build=missing",
                build_command="cmake --build build",
            ),
            "vcpkg.json": DependencyInfo(
                manager="vcpkg", language="c",
                install_command="vcpkg install",
                build_command="cmake --build build",
            ),
            "meson.build": DependencyInfo(
                manager="meson", language="c",
                install_command="meson setup build",
                build_command="meson compile -C build",
            ),
        }
