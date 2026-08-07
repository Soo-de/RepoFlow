"""
Unit tests for LLMClient module (dual provider: Gemini & Groq).
"""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.llm_client import LLMClient


def test_llm_client_requires_api_key():
    client = LLMClient(provider="auto", gemini_api_key="", groq_api_key="")
    with pytest.raises(RuntimeError, match="No valid LLM API key provided"):
        import asyncio
        asyncio.run(client.generate("hello"))


@pytest.mark.asyncio
async def test_llm_client_gemini_success():
    client = LLMClient(gemini_api_key="gemini_key", provider="gemini")

    mock_response_json = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": "name: CI\non: push\njobs: {}"}]
                }
            }
        ]
    }

    mock_httpx_response = MagicMock()
    mock_httpx_response.status_code = 200
    mock_httpx_response.raise_for_status = MagicMock()
    mock_httpx_response.json = MagicMock(return_value=mock_response_json)

    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response
        res = await client.generate("Generate workflow")
        assert res == "name: CI\non: push\njobs: {}"

    await client.close()


@pytest.mark.asyncio
async def test_llm_client_groq_success():
    client = LLMClient(groq_api_key="groq_key", provider="groq")

    mock_response_json = {
        "choices": [
            {
                "message": {"content": "name: CI\non: push\njobs: {}"}
            }
        ]
    }

    mock_httpx_response = MagicMock()
    mock_httpx_response.status_code = 200
    mock_httpx_response.raise_for_status = MagicMock()
    mock_httpx_response.json = MagicMock(return_value=mock_response_json)

    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response
        res = await client.generate("Generate workflow")
        assert res == "name: CI\non: push\njobs: {}"

    await client.close()


@pytest.mark.asyncio
async def test_llm_client_openai_success():
    client = LLMClient(openai_api_key="openai_key", provider="openai")

    mock_response_json = {
        "choices": [
            {
                "message": {"content": "name: CI\non: push\njobs: {}"}
            }
        ]
    }

    mock_httpx_response = MagicMock()
    mock_httpx_response.status_code = 200
    mock_httpx_response.raise_for_status = MagicMock()
    mock_httpx_response.json = MagicMock(return_value=mock_response_json)

    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response
        res = await client.generate("Generate workflow")
        assert res == "name: CI\non: push\njobs: {}"

    await client.close()


@pytest.mark.asyncio
async def test_llm_client_fallback_from_gemini_429_to_groq():
    client = LLMClient(
        gemini_api_key="gemini_key",
        groq_api_key="groq_key",
        provider="auto",
    )

    # Gemini call returns 429
    gemini_429_resp = MagicMock()
    gemini_429_resp.status_code = 429
    request = httpx.Request("POST", "https://generativelanguage.googleapis.com")
    gemini_429_resp.raise_for_status.side_effect = httpx.HTTPStatusError("429", request=request, response=gemini_429_resp)

    # Groq call returns success
    groq_success_resp = MagicMock()
    groq_success_resp.status_code = 200
    groq_success_resp.raise_for_status = MagicMock()
    groq_success_resp.json = MagicMock(return_value={
        "choices": [{"message": {"content": "name: CI\non: push\njobs: {}"}}]
    })

    async def mock_post(url, **kwargs):
        if "generativelanguage.googleapis.com" in url:
            return gemini_429_resp
        return groq_success_resp

    with patch.object(client._client, "post", side_effect=mock_post):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            res = await client.generate("Generate workflow")
            assert res == "name: CI\non: push\njobs: {}"

    await client.close()


@pytest.mark.asyncio
async def test_pipeline_execute_self_correction():
    from app.core.pipeline import execute
    from app.core.pipeline_model import PipelineResult
    from app.core.repo_analysis import RepoAnalysis
    from app.core.platform_detect import Platform

    # Mock settings to have API keys
    with patch("app.core.pipeline.settings") as mock_settings:
        mock_settings.gemini_api_key = "test_key"
        mock_settings.groq_api_key = ""
        mock_settings.openai_api_key = ""
        mock_settings.llm_provider = "gemini"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_settings.groq_model = "llama-3.3-70b-versatile"
        mock_settings.openai_model = "gpt-4o-mini"

        # Mock core services so we do not actually clone or analyze a repo
        with patch("app.core.pipeline.clone", new_callable=AsyncMock) as mock_clone, \
             patch("app.core.pipeline.analyze") as mock_analyze, \
             patch("app.core.pipeline.detect_platform") as mock_detect:

            from app.core.detectors.base import DependencyInfo
            mock_clone.return_value = MagicMock()
            mock_analyze.return_value = RepoAnalysis(
                primary_language="Python",
                dependency_info=DependencyInfo(
                    manager="pip",
                    language="Python",
                    install_command="pip install -r requirements.txt",
                ),
                test_framework="pytest"
            )
            mock_detect.return_value = Platform.GITHUB_ACTIONS

            # Mock LLMClient generate calls: first invalid, second valid
            with patch("app.core.pipeline.LLMClient") as mock_client_class:
                mock_client_instance = AsyncMock()
                mock_client_instance.generate.side_effect = [
                    "invalid yaml output",  # 1st call: invalid YAML syntax
                    """
name: CI
on:
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""  # 2nd call: valid YAML

                ]
                mock_client_class.return_value = mock_client_instance

                # Run execute
                result = await execute(
                    repo_url="https://github.com/user/repo",
                    pat="dummy_pat",
                    platform="github_actions"
                )

                assert isinstance(result, PipelineResult)
                assert result.validation_passed is True
                assert len(result.validation_errors) == 0
                assert "name: CI" in result.yaml_output
                assert mock_client_instance.generate.call_count == 2

