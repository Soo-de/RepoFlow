from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, PlatformSetupInfo, TestInfo
from app.core.platform_detect import Platform


class JavaDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "java"

    @property
    def default_runtime_version(self) -> str:
        return "17"

    @property
    def platform_setups(self) -> dict[Platform, PlatformSetupInfo]:
        return {
            Platform.GITHUB_ACTIONS: PlatformSetupInfo(
                "actions/setup-java@v4", "java-version", extra_inputs={"distribution": "temurin"}
            ),
            Platform.AZURE_PIPELINES: PlatformSetupInfo(
                "JavaToolInstaller@0", "versionSpec", extra_inputs={"jdkArchitectureOption": "x64", "jdkSourceOption": "PreInstalled"}
            ),
        }

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
                publish_command="mvn package -DskipTests",
                manifest_file="pom.xml",
                lockfile="pom.xml",
                cache_path="$(Pipeline.Workspace)/.m2/repository",
            ),
            "build.gradle": DependencyInfo(
                manager="gradle", language="java",
                install_command="gradle build -x test",
                build_command="gradle build -x test",
                publish_command="gradle build -x test",
                manifest_file="build.gradle",
                cache_path="$(Pipeline.Workspace)/.gradle",
            ),
            "build.gradle.kts": DependencyInfo(
                manager="gradle", language="java",
                install_command="gradle build -x test",
                build_command="gradle build -x test",
                publish_command="gradle build -x test",
                manifest_file="build.gradle.kts",
                cache_path="$(Pipeline.Workspace)/.gradle",
            ),
        }

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        lockfile = base_info.lockfile
        if matched_marker in ("build.gradle", "build.gradle.kts"):
            if (directory / "gradle.lockfile").exists():
                lockfile = "gradle.lockfile"

        return DependencyInfo(
            manager=base_info.manager,
            language=base_info.language,
            install_command=base_info.install_command,
            build_command=base_info.build_command,
            publish_command=base_info.publish_command,
            manifest_file=base_info.manifest_file or matched_marker,
            lockfile=lockfile,
            cache_path=base_info.cache_path,
            runner_image="eclipse-temurin:21-jre",
            runner_entrypoint="java -jar app.jar",
            app_type="runtime_service",
            publish_dir="target",
        )

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
