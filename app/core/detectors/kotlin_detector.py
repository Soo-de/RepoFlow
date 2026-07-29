from app.core.detectors.base import BaseDetector, DependencyInfo


class KotlinDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "kotlin"

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
