"""
Unit tests for LLMClient module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.llm_client import LLMClient


def test_llm_client_requires_api_key():
    with pytest.raises(ValueError, match="Gemini API key is required"):
        LLMClient(api_key="")


@pytest.mark.asyncio
async def test_llm_client_generate_success():
    client = LLMClient(api_key="test_key")

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
    mock_httpx_response.raise_for_status = MagicMock()
    mock_httpx_response.json = MagicMock(return_value=mock_response_json)

    with patch.object(client._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_httpx_response

        res = await client.generate("Generate workflow")
        assert res == "name: CI\non: push\njobs: {}"
        mock_post.assert_called_once()

    await client.close()
