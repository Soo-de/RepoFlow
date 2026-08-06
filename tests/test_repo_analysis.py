"""
Unit tests for repo_analysis module.
"""

from app.core.repo_analysis import analyze


def test_analyze_python_project(tmp_path):
    # Setup mock repository files
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "utils.py").write_text("def add(a, b): return a + b", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nrequires-python = "3.11"\ndependencies = ["pytest", "psycopg2"]',
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("psycopg2\npytest", encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.primary_language == "python"
    assert analysis.dependency_manager == "pip"
    assert analysis.runtime_version == "3.11"
    assert analysis.test_framework == "pytest"
    assert "postgres" in analysis.services_needed
    assert "main.py" in analysis.entry_points


def test_python_project_default_version_isolated_from_node(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("requests", encoding="utf-8")
    # Add a package.json to mimic a mixed directory or frontend assets subfolder
    (tmp_path / "package.json").write_text('{"name": "assets", "engines": {"node": "20.x"}}', encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.primary_language == "python"
    # Should use Python's default version (3.12), NOT Node's 20.x
    assert analysis.runtime_version == "3.12"


def test_analyze_node_project(tmp_path):
    (tmp_path / "index.ts").write_text("console.log('hi');", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        '{"name": "app", "scripts": {"test": "jest"}, "devDependencies": {"jest": "^29.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / "package-lock.json").write_text('{"name": "app"}', encoding="utf-8")
    (tmp_path / ".nvmrc").write_text("18.16.0", encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.primary_language == "typescript"
    assert analysis.dependency_manager == "npm"
    assert analysis.install_command == "npm ci"
    assert analysis.runtime_version == "18.16.0"
    assert analysis.test_framework == "jest"
    assert analysis.lockfile == "package-lock.json"


def test_analyze_node_project_default_version(tmp_path):
    (tmp_path / "index.js").write_text("console.log('hello');", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name": "app"}', encoding="utf-8")

    analysis = analyze(tmp_path)

    # When no .nvmrc or engines field is defined, default to 20 LTS
    assert analysis.primary_language == "javascript"
    assert analysis.runtime_version == "20"
    # When package-lock.json is missing, fall back to npm install instead of npm ci
    assert analysis.install_command == "npm install"
    assert analysis.lockfile is None


def test_analyze_dockerfile_and_ci_configs(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.11", encoding="utf-8")
    workflows_dir = tmp_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "ci.yml").write_text("name: CI", encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.has_dockerfile is True
    assert ".github/workflows/ci.yml" in analysis.existing_pipeline_files


def test_analyze_csharp_project_with_sln(tmp_path):
    (tmp_path / "App.sln").write_text("Microsoft Visual Studio Solution File, Format Version 12.00", encoding="utf-8")
    subfolder = tmp_path / "WebApi"
    subfolder.mkdir()
    (subfolder / "WebApi.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>', encoding="utf-8")
    (subfolder / "Program.cs").write_text("var builder = WebApplication.CreateBuilder(args);", encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.primary_language == "csharp"
    assert analysis.dependency_manager == "dotnet"
    assert analysis.runtime_version == "10.0.x"
    assert analysis.install_command == "dotnet restore App.sln"
    assert analysis.build_command == "dotnet build App.sln --configuration Release --no-restore"
    assert analysis.publish_command == "dotnet publish App.sln --configuration Release -o /app/publish"
    assert "WebApi/WebApi.csproj" in analysis.additional_manifests
    assert analysis.runner_entrypoint == "dotnet WebApi.dll"
    assert analysis.services_needed == []


def test_analyze_csharp_service_detection(tmp_path):
    # Embedded/in-process DBs like SQLite require no external service container
    (tmp_path / "App.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk.Web">'
        '<ItemGroup>'
        '<PackageReference Include="Microsoft.EntityFrameworkCore.SqlServer" Version="8.0.0" />'
        '<PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="8.0.0" />'
        '</ItemGroup>'
        '</Project>',
        encoding="utf-8"
    )

    analysis = analyze(tmp_path)

    # SqlServer triggers external 'mssql' service, while embedded Sqlite is ignored for services
    assert "mssql" in analysis.services_needed
    assert "sqlite" not in analysis.services_needed


def test_analyze_csharp_project_nested_without_sln(tmp_path):
    subfolder = tmp_path / "WebApi"
    subfolder.mkdir()
    (subfolder / "WebApi.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>', encoding="utf-8")
    (subfolder / "Program.cs").write_text("var builder = WebApplication.CreateBuilder(args);", encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.primary_language == "csharp"
    assert analysis.working_dir == "WebApi"
    assert analysis.install_command == "dotnet restore WebApi.csproj"
    assert analysis.build_command == "dotnet build WebApi.csproj --configuration Release --no-restore"
    assert analysis.publish_command == "dotnet publish WebApi.csproj --configuration Release -o /app/publish"


def test_analyze_csharp_project_with_slnx(tmp_path):
    (tmp_path / "App.slnx").write_text('<Solution></Solution>', encoding="utf-8")
    subfolder = tmp_path / "WebApi"
    subfolder.mkdir()
    (subfolder / "WebApi.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>', encoding="utf-8")
    (subfolder / "Program.cs").write_text("var builder = WebApplication.CreateBuilder(args);", encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.primary_language == "csharp"
    assert analysis.dependency_manager == "dotnet"
    assert analysis.manifest_file == "App.slnx"
    assert analysis.install_command == "dotnet restore App.slnx"
    assert analysis.build_command == "dotnet build App.slnx --configuration Release --no-restore"
    assert analysis.publish_command == "dotnet publish App.slnx --configuration Release -o /app/publish"
    assert analysis.runner_entrypoint == "dotnet WebApi.dll"


def test_analyze_nested_node_project(tmp_path):
    subfolder = tmp_path / "cinelog"
    subfolder.mkdir()
    (subfolder / "index.js").write_text("console.log('hi');", encoding="utf-8")
    (subfolder / "package.json").write_text('{"name": "cinelog"}', encoding="utf-8")
    (subfolder / "package-lock.json").write_text('{"name": "cinelog"}', encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.primary_language == "javascript"
    assert analysis.dependency_manager == "npm"
    assert analysis.working_dir == "cinelog"
    assert analysis.manifest_file == "cinelog/package.json"
    assert analysis.install_command == "npm ci"
    assert analysis.lockfile == "cinelog/package-lock.json"


def test_analyze_node_lockfile_version_signals(tmp_path):
    # Lockfile v1 -> Node 14
    (tmp_path / "package.json").write_text('{"name": "legacy-app"}', encoding="utf-8")
    (tmp_path / "package-lock.json").write_text('{"name": "legacy-app", "lockfileVersion": 1}', encoding="utf-8")
    analysis = analyze(tmp_path)
    assert analysis.runtime_version == "14"

    # Lockfile v2 -> Node 16
    (tmp_path / "package-lock.json").write_text('{"name": "legacy-app", "lockfileVersion": 2}', encoding="utf-8")
    analysis_v2 = analyze(tmp_path)
    assert analysis_v2.runtime_version == "16"

    # Lockfile v3 -> default 20
    (tmp_path / "package-lock.json").write_text('{"name": "legacy-app", "lockfileVersion": 3}', encoding="utf-8")
    analysis_v3 = analyze(tmp_path)
    assert analysis_v3.runtime_version == "20"

    # Lockfile v1 + --openssl-legacy-provider in package.json -> elevated to Node 18
    pkg_openssl = '{"name": "corona", "scripts": {"build": "NODE_OPTIONS=--openssl-legacy-provider ng build"}}'
    (tmp_path / "package.json").write_text(pkg_openssl, encoding="utf-8")
    (tmp_path / "package-lock.json").write_text('{"name": "corona", "lockfileVersion": 1}', encoding="utf-8")
    analysis_openssl = analyze(tmp_path)
    assert analysis_openssl.runtime_version == "18"


def test_generic_script_env_var_scanner(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "script-app"}', encoding="utf-8")
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "check_env.sh").write_text('if [ -z "$CUSTOM_STAGE_ENV" ]; then exit 1; fi', encoding="utf-8")

    analysis = analyze(tmp_path)
    env_keys = [req.key for req in analysis.environment_requirements if req.kind == "env_var"]
    assert "CUSTOM_STAGE_ENV" in env_keys









