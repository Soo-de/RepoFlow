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
