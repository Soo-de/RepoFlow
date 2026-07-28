from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, TestInfo


class CSharpDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "csharp"

    @property
    def extension_map(self) -> dict[str, str]:
        return {
            ".cs": "csharp",
            ".csproj": "csharp",
            ".sln": "csharp",
        }

    @property
    def dependency_markers(self) -> dict[str, DependencyInfo]:
        return {
            "global.json": DependencyInfo(
                manager="dotnet", language="csharp",
                install_command="dotnet restore",
                build_command="dotnet build --configuration Release --no-restore",
                manifest_file="global.json",
                cache_path="$(Pipeline.Workspace)/.nuget/packages",
                cache_env_var="NUGET_PACKAGES",
            ),
            "packages.config": DependencyInfo(
                manager="nuget", language="csharp",
                install_command="nuget restore",
                build_command="msbuild /p:Configuration=Release",
                manifest_file="packages.config",
                cache_path="$(Pipeline.Workspace)/.nuget/packages",
                cache_env_var="NUGET_PACKAGES",
            ),
            "NuGet.Config": DependencyInfo(
                manager="dotnet", language="csharp",
                install_command="dotnet restore",
                build_command="dotnet build --configuration Release --no-restore",
                manifest_file="NuGet.Config",
                cache_path="$(Pipeline.Workspace)/.nuget/packages",
                cache_env_var="NUGET_PACKAGES",
            ),
        }

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["Program.cs", "Startup.cs"]

    @property
    def monorepo_markers(self) -> list[str]:
        return ["*.csproj"]

    def detect_dependency_info(self, directory: Path) -> DependencyInfo | None:
        """Custom check for .csproj and .sln files in the directory."""
        csproj_files = list(directory.glob("*.csproj"))
        sln_files = list(directory.glob("*.sln"))

        if csproj_files or sln_files:
            manifest = csproj_files[0].name if csproj_files else sln_files[0].name
            return DependencyInfo(
                manager="dotnet",
                language="csharp",
                install_command="dotnet restore",
                build_command="dotnet build --configuration Release --no-restore",
                manifest_file=manifest,
                cache_path="$(Pipeline.Workspace)/.nuget/packages",
                cache_env_var="NUGET_PACKAGES",
            )
        return None

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        resolved = self.detect_dependency_info(directory)
        return resolved or base_info

    def detect_test_framework(self, directory: Path) -> TestInfo | None:
        # Check if any test projects exist (*Tests.csproj or *Test.csproj)
        test_projects = list(directory.rglob("*Test*.csproj")) + list(directory.rglob("*test*.csproj"))
        if test_projects:
            return TestInfo(framework="dotnet_test", command="dotnet test --no-build --logger trx")
        return None
