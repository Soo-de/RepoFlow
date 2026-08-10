from pathlib import Path

from app.core.detectors.base import BaseDetector, DependencyInfo, PlatformSetupInfo, TestInfo, ServiceHint
from app.core.platform_detect import Platform


class CSharpDetector(BaseDetector):

    @property
    def language(self) -> str:
        return "csharp"

    @property
    def default_runtime_version(self) -> str:
        return "8.0"

    @property
    def platform_setups(self) -> dict[Platform, PlatformSetupInfo]:
        return {
            Platform.GITHUB_ACTIONS: PlatformSetupInfo("actions/setup-dotnet@v4", "dotnet-version"),
            Platform.AZURE_PIPELINES: PlatformSetupInfo("UseDotNet@2", "version", extra_inputs={"packageType": "sdk"}),
        }

    @property
    def extension_map(self) -> dict[str, str]:
        return {
            ".cs": "csharp",
            ".csproj": "csharp",
            ".sln": "csharp",
            ".slnx": "csharp",
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
    def service_hints(self) -> list[ServiceHint]:
        return [
            ServiceHint("Microsoft.EntityFrameworkCore.SqlServer", "mssql"),
            ServiceHint("Microsoft.Data.SqlClient", "mssql"),
            ServiceHint("System.Data.SqlClient", "mssql"),
            ServiceHint("Npgsql", "postgres"),
            ServiceHint("Pomelo.EntityFrameworkCore.MySql", "mysql"),
            ServiceHint("MySql.Data", "mysql"),
            ServiceHint("StackExchange.Redis", "redis"),
            ServiceHint("MongoDB.Driver", "mongodb"),
        ]

    @property
    def dep_files_for_service_scan(self) -> list[str]:
        return ["*.csproj", "packages.config"]

    @property
    def entry_point_patterns(self) -> list[str]:
        return ["Program.cs", "Startup.cs"]

    @property
    def monorepo_markers(self) -> list[str]:
        return ["*.csproj", "*.sln", "*.slnx"]

    def detect_dependency_info(self, directory: Path) -> DependencyInfo | None:
        """Recursive check for .csproj, .sln, and .slnx files in the directory or subdirectories."""
        csproj_files = sorted(
            [f for f in directory.rglob("*.csproj") if not any(skip in f.parts for skip in (".git", "bin", "obj", "node_modules"))],
            key=lambda f: len(f.relative_to(directory).parts)
        )
        sln_files = sorted(
            [f for f in directory.rglob("*.sln") if not any(skip in f.parts for skip in (".git", "bin", "obj", "node_modules"))],
            key=lambda f: len(f.relative_to(directory).parts)
        )
        slnx_files = sorted(
            [f for f in directory.rglob("*.slnx") if not any(skip in f.parts for skip in (".git", "bin", "obj", "node_modules"))],
            key=lambda f: len(f.relative_to(directory).parts)
        )

        if slnx_files:
            target_file = slnx_files[0]
        elif sln_files:
            target_file = sln_files[0]
        elif csproj_files:
            target_file = csproj_files[0]
        else:
            return None

        try:
            rel_path = target_file.relative_to(directory).as_posix()
        except ValueError:
            rel_path = target_file.name

        working_dir = rel_path.rsplit("/", 1)[0] if "/" in rel_path else None

        # When working_dir is set (nested project/sln), commands can be run directly inside working_dir
        if working_dir:
            file_name = rel_path.rsplit("/", 1)[1]
            install_cmd = f"dotnet restore {file_name}"
            build_cmd = f"dotnet build {file_name} --configuration Release --no-restore"
            publish_cmd = f"dotnet publish {file_name} --configuration Release -o ./publish"
        else:
            install_cmd = f"dotnet restore {rel_path}"
            build_cmd = f"dotnet build {rel_path} --configuration Release --no-restore"
            publish_cmd = f"dotnet publish {rel_path} --configuration Release -o ./publish"

        lockfile = "packages.lock.json" if (directory / "packages.lock.json").exists() else None

        entrypoint = self._resolve_entrypoint_dll(target_file, csproj_files)

        # If a solution file (.sln / .slnx) is selected, include referenced .csproj project files as additional manifests
        additional_manifests: list[str] = []
        if target_file.suffix in (".sln", ".slnx"):
            for csproj in csproj_files:
                try:
                    additional_manifests.append(csproj.relative_to(directory).as_posix())
                except ValueError:
                    additional_manifests.append(csproj.name)

        # .csproj/.fsproj files contain <PackageReference> with version pins;
        # .sln/.slnx only list project paths and must not be used for cache keys
        cache_key_files = [
            csproj.relative_to(directory).as_posix() for csproj in csproj_files
        ]
        fsproj_files = sorted(
            [f for f in directory.rglob("*.fsproj") if not any(skip in f.parts for skip in (".git", "bin", "obj", "node_modules"))],
            key=lambda f: len(f.relative_to(directory).parts)
        )
        cache_key_files.extend(
            f.relative_to(directory).as_posix() for f in fsproj_files
        )

        return DependencyInfo(
            manager="dotnet",
            language="csharp",
            install_command=install_cmd,
            build_command=build_cmd,
            publish_command=publish_cmd,
            manifest_file=rel_path,
            lockfile=lockfile,
            working_dir=working_dir,
            cache_path="$(Pipeline.Workspace)/.nuget/packages",
            cache_env_var="NUGET_PACKAGES",
            runner_image="mcr.microsoft.com/dotnet/aspnet:10.0",
            runner_entrypoint=entrypoint,
            app_type="runtime_service",
            publish_dir="publish",
            additional_manifests=additional_manifests,
            cache_key_files=cache_key_files,
        )

    def resolve_dependency_info(
        self, directory: Path, matched_marker: str, base_info: DependencyInfo,
    ) -> DependencyInfo:
        resolved = self.detect_dependency_info(directory)
        return resolved or base_info

    def detect_test_framework(self, directory: Path) -> TestInfo | None:
        # Stop early if no test source files or test folders exist on disk
        if not self.has_test_files(directory):
            return None

        # Look for .csproj/.fsproj/.vbproj test projects or NuGet test package references
        test_package_markers = ("microsoft.net.test.sdk", "xunit", "nunit", "mstest", "bunit")

        test_projects = []
        for proj in directory.rglob("*.[cfv]sproj"):
            if any(skip in proj.parts for skip in (".git", "bin", "obj", "node_modules")):
                continue
            name_lower = proj.name.lower()
            if any(token in name_lower for token in ("test", "spec")):
                test_projects.append(proj)
            else:
                try:
                    content = proj.read_text(encoding="utf-8", errors="ignore").lower()
                    if any(pkg in content for pkg in test_package_markers):
                        test_projects.append(proj)
                except Exception:
                    pass

        test_dirs = [
            d for d in directory.rglob("*")
            if d.is_dir() and any(token in d.name.lower() for token in ("test", "tests", "spec", "specs"))
            and not any(skip in d.parts for skip in (".git", "bin", "obj", "node_modules"))
            and any(f.suffix in (".cs", ".fs", ".vb") for f in d.rglob("*"))
        ]

        if test_projects or test_dirs:
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

    def _resolve_entrypoint_dll(self, target_file: Path, csproj_files: list[Path]) -> str:
        """Determine the main executable DLL name.

        For solution files (.sln / .slnx), inspect project files to find the web or
        executable application assembly containing Program.cs/Startup.cs or Web SDKs.
        """
        if target_file.suffix == ".csproj" or not csproj_files:
            return f"dotnet {target_file.stem}.dll"

        # 1. Search for .csproj in directory containing Program.cs or Startup.cs
        for csproj in csproj_files:
            csproj_dir = csproj.parent
            if (csproj_dir / "Program.cs").exists() or (csproj_dir / "Startup.cs").exists():
                return f"dotnet {csproj.stem}.dll"

        # 2. Search for .csproj using Web SDK or Executable output type
        for csproj in csproj_files:
            try:
                content = csproj.read_text(encoding="utf-8")
                if "Microsoft.NET.Sdk.Web" in content or "<OutputType>Exe</OutputType>" in content:
                    return f"dotnet {csproj.stem}.dll"
            except OSError:
                continue

        # 3. Search for .csproj with Web, Api, UI, App, or Server in project stem
        for csproj in csproj_files:
            name_lower = csproj.stem.lower()
            if any(token in name_lower for token in ("web", "api", "ui", "app", "server", "service")):
                return f"dotnet {csproj.stem}.dll"

        # 4. Fallback to the first project or target stem
        return f"dotnet {csproj_files[0].stem}.dll"

