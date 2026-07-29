from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, TestInfo


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
                build_command="mvn package -DskipTests",
                manifest_file="pom.xml",
                cache_path="$(Pipeline.Workspace)/.m2/repository",
            ),
            "build.gradle": DependencyInfo(
                manager="gradle", language="java",
                install_command="gradle build -x test",
                build_command="gradle build -x test",
                manifest_file="build.gradle",
                cache_path="$(Pipeline.Workspace)/.gradle",
            ),
            "build.gradle.kts": DependencyInfo(
                manager="gradle", language="java",
                install_command="gradle build -x test",
                build_command="gradle build -x test",
                manifest_file="build.gradle.kts",
                cache_path="$(Pipeline.Workspace)/.gradle",
            ),
        }

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["Main.java"]

    @property
    def monorepo_markers(self) -> list[str]:
        return ["pom.xml", "build.gradle"]

    def detect_test_framework(self, directory: Path) -> TestInfo | None:
        if (directory / "pom.xml").exists():
            return TestInfo(framework="junit", command="mvn test")
        if (directory / "build.gradle").exists() or (directory / "build.gradle.kts").exists():
            return TestInfo(framework="junit", command="gradle test")
        
        test_dirs = [d for d in directory.rglob("src/test") if d.is_dir()]
        if test_dirs:
            return TestInfo(framework="junit", command="mvn test")
        return None
