from app.core.detectors.base import BaseDetector, DependencyInfo


class SwiftDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "swift"

    @property
    def extension_map(self) -> dict[str, str]:
        return {".swift": "swift"}

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "Package.swift": DependencyInfo(
                manager="spm", language="swift",
                install_command="swift package resolve",
            ),
        }
