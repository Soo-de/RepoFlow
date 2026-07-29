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


def test_analyze_node_project(tmp_path):
    (tmp_path / "index.ts").write_text("console.log('hi');", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        '{"name": "app", "scripts": {"test": "jest"}, "devDependencies": {"jest": "^29.0.0"}}',
        encoding="utf-8",
    )
    (tmp_path / ".nvmrc").write_text("18.16.0", encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.primary_language == "typescript"
    assert analysis.dependency_manager == "npm"
    assert analysis.runtime_version == "18.16.0"
    assert analysis.test_framework == "jest"


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


def test_analyze_csharp_project_with_slnx(tmp_path):
    (tmp_path / "App.slnx").write_text('<Solution></Solution>', encoding="utf-8")
    subfolder = tmp_path / "WebApi"
    subfolder.mkdir()
    (subfolder / "WebApi.csproj").write_text('<Project Sdk="Microsoft.NET.Sdk.Web"><PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup></Project>', encoding="utf-8")
    (subfolder / "Program.cs").write_text("var builder = WebApplication.CreateBuilder(args);", encoding="utf-8")

    analysis = analyze(tmp_path)

    assert analysis.primary_language == "csharp"
    assert analysis.dependency_manager == "dotnet"
    assert analysis.manifest_file == "WebApi/WebApi.csproj"
    assert analysis.working_dir == "WebApi"
    assert analysis.install_command == "dotnet restore WebApi.csproj"
    assert analysis.build_command == "dotnet build WebApi.csproj --configuration Release --no-restore"








