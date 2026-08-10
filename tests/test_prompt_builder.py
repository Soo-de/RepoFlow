"""
Unit tests for PromptBuilder module.
"""

from app.core.detectors.base import DependencyInfo
from app.core.platform_detect import Platform
from app.core.repo_analysis import RepoAnalysis
from app.core.prompt_builder import PromptBuilder


def test_prompt_builder_github_actions():
    builder = PromptBuilder()
    analysis = RepoAnalysis(
        primary_language="Python",
        dependency_info=DependencyInfo(
            manager="pip",
            language="Python",
            install_command="pip install -r requirements.txt",
            build_command="pip install -e .",
        ),
        test_framework="pytest",
        test_command="pytest",
        runtime_version="3.11",
        services_needed=["postgres"],
        has_dockerfile=True,
    )
    prompt = builder.build(Platform.GITHUB_ACTIONS, analysis)
    assert "Python" in prompt
    assert "pytest" in prompt
    assert "postgres" in prompt
    assert "GitHub Actions" in prompt


def test_prompt_builder_azure_pipelines():
    builder = PromptBuilder()
    analysis = RepoAnalysis(
        primary_language="Node.js",
        dependency_info=DependencyInfo(
            manager="npm",
            language="Node.js",
            install_command="npm ci",
        ),
        test_framework="jest",
        test_command="npm test",
    )
    prompt = builder.build(Platform.AZURE_PIPELINES, analysis)
    assert "Node.js" in prompt
    assert "npm test" in prompt
    assert "Azure Pipelines" in prompt


def test_prompt_builder_correction():
    builder = PromptBuilder()
    invalid_yaml = "invalid: yaml: structure"
    errors = ["Schema Error: 'jobs' is required", "YAML Syntax Error: unclosed block"]
    prompt = builder.build_correction(invalid_yaml, errors)
    assert "invalid: yaml: structure" in prompt
    assert "Schema Error: 'jobs' is required" in prompt
    assert "YAML Syntax Error: unclosed block" in prompt


def test_prompt_builder_dockerfile_csharp():
    builder = PromptBuilder()
    analysis = RepoAnalysis(
        primary_language="csharp",
        dependency_info=DependencyInfo(
            manager="dotnet",
            language="csharp",
            install_command="dotnet restore App.sln",
            manifest_file="App.sln",
            additional_manifests=["WebApi/WebApi.csproj"],
            publish_dir="publish",
            runner_image="mcr.microsoft.com/dotnet/aspnet:10.0",
            runner_entrypoint="dotnet WebApi.dll",
            app_type="runtime_service",
        ),
    )
    prompt = builder.build_dockerfile(analysis)
    assert "Primary Language: csharp" in prompt
    assert "mcr.microsoft.com/dotnet/aspnet:10.0" in prompt
    assert "dotnet WebApi.dll" in prompt


