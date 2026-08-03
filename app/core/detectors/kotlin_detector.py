from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, PlatformSetupInfo
from app.core.platform_detect import Platform


class KotlinDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "kotlin"

    @property
    def platform_setups(self) -> dict[Platform, PlatformSetupInfo]:
        return {
            Platform.GITHUB_ACTIONS: PlatformSetupInfo("actions/setup-java@v4", "java-version"),
            Platform.AZURE_PIPELINES: PlatformSetupInfo("JavaToolInstaller@0", "versionSpec"),
        }

    @property
    def extension_map(self) -> dict[str, str]:
        return {".kt": "kotlin"}

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "build.gradle.kts": DependencyInfo(
                manager="gradle", language="kotlin",
                install_command="gradle build",
                build_command="gradle build",
            ),
        }
