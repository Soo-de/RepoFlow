from app.core.detectors.base import BaseDetector, DependencyInfo


class JavaDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "java"

    @property
    def extension_map(self) -> dict[str, str]:
        return {".java": "java"}

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "pom.xml": DependencyInfo(
                manager="maven", language="java",
                install_command="mvn install",
                build_command="mvn package",
            ),
            "build.gradle": DependencyInfo(
                manager="gradle", language="java",
                install_command="gradle build",
                build_command="gradle build",
            ),
        }

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["Main.java"]

    @property
    def monorepo_markers(self) -> list[str]:
        return ["pom.xml"]
