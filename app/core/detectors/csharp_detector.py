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
                azure_setup_task="UseDotNet@2",
                azure_version_key="version",
                github_setup_action="actions/setup-dotnet@v4",
                github_version_key="dotnet-version",
            ),
            "packages.config": DependencyInfo(
                manager="nuget", language="csharp",
                install_command="nuget restore",
                build_command="msbuild /p:Configuration=Release",
                manifest_file="packages.config",
                cache_path="$(Pipeline.Workspace)/.nuget/packages",
                cache_env_var="NUGET_PACKAGES",
                azure_setup_task="UseDotNet@2",
                azure_version_key="version",
                github_setup_action="actions/setup-dotnet@v4",
                github_version_key="dotnet-version",
            ),
            "NuGet.Config": DependencyInfo(
                manager="dotnet", language="csharp",
                install_command="dotnet restore",
                build_command="dotnet build --configuration Release --no-restore",
                manifest_file="NuGet.Config",
                cache_path="$(Pipeline.Workspace)/.nuget/packages",
                cache_env_var="NUGET_PACKAGES",
                azure_setup_task="UseDotNet@2",
                azure_version_key="version",
                github_setup_action="actions/setup-dotnet@v4",
                github_version_key="dotnet-version",
            ),
        }

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["Program.cs", "Startup.cs"]

    @property
    def monorepo_markers(self) -> list[str]:
        return ["*.csproj"]

    def detect_dependency_info(self, directory: Path) -> DependencyInfo | None:
        """Recursive check for .csproj and .sln files in the directory or subdirectories."""
        csproj_files = [f for f in directory.rglob("*.csproj") if not any(skip in f.parts for skip in (".git", "bin", "obj", "node_modules"))]
        sln_files = [f for f in directory.rglob("*.sln") if not any(skip in f.parts for skip in (".git", "bin", "obj", "node_modules"))]

        if csproj_files or sln_files:
            target_file = sln_files[0] if sln_files else csproj_files[0]
            try:
                rel_path = target_file.relative_to(directory).as_posix()
            except ValueError:
                rel_path = target_file.name

            # Include target path in commands if nested in a subfolder
            install_cmd = f"dotnet restore {rel_path}" if "/" in rel_path else "dotnet restore"
            build_cmd = f"dotnet build {rel_path} --configuration Release --no-restore" if "/" in rel_path else "dotnet build --configuration Release --no-restore"

            return DependencyInfo(
                manager="dotnet",
                language="csharp",
                install_command=install_cmd,
                build_command=build_cmd,
                manifest_file=rel_path,
                cache_path="$(Pipeline.Workspace)/.nuget/packages",
                cache_env_var="NUGET_PACKAGES",
                azure_setup_task="UseDotNet@2",
                azure_version_key="version",
                github_setup_action="actions/setup-dotnet@v4",
                github_version_key="dotnet-version",
            )
        return None

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        resolved = self.detect_dependency_info(directory)
        return resolved or base_info

    def detect_test_framework(self, directory: Path) -> TestInfo | None:
        # Search recursively for test projects or test directories
        test_projects = [f for f in directory.rglob("*.csproj") if any(token in f.name.lower() for token in ("test", "spec"))]
        test_dirs = [d for d in directory.rglob("*") if d.is_dir() and d.name.lower() in ("test", "tests", "specs")]

        if test_projects or test_dirs:
            return TestInfo(framework="dotnet_test", command="dotnet test --no-build --logger trx")

        # If any .csproj exists, default to dotnet test
        all_projects = [f for f in directory.rglob("*.csproj") if not any(skip in f.parts for skip in (".git", "bin", "obj", "node_modules"))]
        if all_projects:
            return TestInfo(framework="dotnet_test", command="dotnet test --no-build --logger trx")

        return None

    def detect_runtime_version(self, repo_dir: Path) -> str | None:
        import re

        # 1. Check global.json
        global_json = repo_dir / "global.json"
        if global_json.exists():
            try:
                import json
                data = json.loads(global_json.read_text(encoding="utf-8"))
                version = data.get("sdk", {}).get("version")
                if version:
                    return version
            except Exception:
                pass

        # 2. Check Directory.Build.props / Directory.Build.targets at root
        for prop_name in ("Directory.Build.props", "Directory.Build.targets"):
            prop_file = repo_dir / prop_name
            if prop_file.exists():
                try:
                    content = prop_file.read_text(encoding="utf-8")
                    match = re.search(r"<TargetFrameworks?>\s*(?:net(?:coreapp)?)?(\d+\.\d+)", content, re.IGNORECASE)
                    if match:
                        return f"{match.group(1)}.x"
                except Exception:
                    pass

        # 3. Check .csproj files for <TargetFramework> or <TargetFrameworks>
        for csproj in repo_dir.rglob("*.csproj"):
            if any(skip in csproj.parts for skip in (".git", "bin", "obj", "node_modules")):
                continue
            try:
                content = csproj.read_text(encoding="utf-8")
                # Matches <TargetFramework>net6.0</TargetFramework>, <TargetFrameworks>net8.0;net7.0</TargetFrameworks>, netcoreapp3.1, etc.
                match = re.search(r"<TargetFrameworks?>\s*(?:net(?:coreapp)?)?(\d+\.\d+)", content, re.IGNORECASE)
                if match:
                    return f"{match.group(1)}.x"
                match_old = re.search(r"<TargetFrameworkVersion>\s*v?(\d+\.\d+)", content, re.IGNORECASE)
                if match_old:
                    return match_old.group(1)
            except Exception:
                pass

        return None
