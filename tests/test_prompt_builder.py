"""
Unit tests for PromptBuilder module.
"""

from app.core.platform_detect import Platform
from app.core.repo_analysis import RepoAnalysis
from app.core.prompt_builder import PromptBuilder


def test_prompt_builder_github_actions():
    builder = PromptBuilder()
    analysis = RepoAnalysis(
        primary_language="Python",
        dependency_manager="pip",
        test_framework="pytest",
        build_command="pip install -e .",
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
        dependency_manager="npm",
        test_framework="jest",
        test_command="npm test",
    )
    prompt = builder.build(Platform.AZURE_PIPELINES, analysis)
    assert "Node.js" in prompt
    assert "npm test" in prompt
    assert "Azure Pipelines" in prompt
