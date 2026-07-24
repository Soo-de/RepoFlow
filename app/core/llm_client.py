import logging
import httpx

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.0-flash"


class LLMClient:
    """Thin async wrapper around the Gemini REST API.

    This is the only module in the project that makes LLM calls.
    It knows nothing about YAML, platforms, or pipelines — it takes
    a prompt string and returns a response string.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")

        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(timeout=60.0)

    async def generate(self, prompt: str) -> str:
        """Send a prompt to Gemini and return the text response."""
        url = f"{GEMINI_API_URL}/{self._model}:generateContent"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096,
            },
        }

        response = await self._client.post(
            url,
            params={"key": self._api_key},
            json=payload,
        )
        response.raise_for_status()

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError("Gemini returned empty response")

        return parts[0].get("text", "")

    async def close(self) -> None:
        await self._client.aclose()
