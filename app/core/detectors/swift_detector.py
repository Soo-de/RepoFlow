from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, PlatformSetupInfo
from app.core.platform_detect import Platform


class SwiftDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "swift"

    @property
    def platform_setups(self) -> dict[Platform, PlatformSetupInfo]:
        return {
            Platform.GITHUB_ACTIONS: PlatformSetupInfo("swift-actions/setup-swift@v2", "swift-version"),
        }

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
