import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
MAX_RETRIES = 2


class LLMClient:
    """Multi-provider async LLM client supporting Gemini, Groq, and OpenAI with automatic fallback."""

    def __init__(
        self,
        gemini_api_key: str = "",
        groq_api_key: str = "",
        openai_api_key: str = "",
        provider: str = "auto",
        gemini_model: str = DEFAULT_GEMINI_MODEL,
        groq_model: str = DEFAULT_GROQ_MODEL,
        openai_model: str = DEFAULT_OPENAI_MODEL,
    ) -> None:
        self._gemini_key = gemini_api_key.strip()
        self._groq_key = groq_api_key.strip()
        self._openai_key = openai_api_key.strip()
        self._provider = provider.lower().strip()
        self._gemini_model = gemini_model
        self._groq_model = groq_model
        self._openai_model = openai_model
        self._client = httpx.AsyncClient(timeout=60.0)

    async def generate(self, prompt: str) -> str:
        """Generate response string from Gemini, Groq, OpenAI, or automatic fallback."""
        if self._provider == "gemini":
            return await self._generate_gemini(prompt)

        if self._provider == "groq":
            return await self._generate_groq(prompt)

        if self._provider == "openai":
            return await self._generate_openai(prompt)

        # Auto mode: Try Gemini first, fall back to Groq then OpenAI on missing key or 429 rate limit
        if self._gemini_key:
            try:
                logger.info("Attempting pipeline generation via Gemini API...")
                return await self._generate_gemini(prompt)
            except RuntimeError as err:
                if ("rate limit" in str(err).lower() or "429" in str(err)):
                    if self._groq_key:
                        logger.warning("Gemini hit rate limit (429). Falling back to Groq API...")
                        return await self._generate_groq(prompt)
                    if self._openai_key:
                        logger.warning("Gemini hit rate limit (429). Falling back to OpenAI API...")
                        return await self._generate_openai(prompt)
                raise

        if self._groq_key:
            try:
                logger.info("Gemini key not set. Generating via Groq API...")
                return await self._generate_groq(prompt)
            except RuntimeError as err:
                if self._openai_key and ("rate limit" in str(err).lower() or "429" in str(err)):
                    logger.warning("Groq hit rate limit (429). Falling back to OpenAI API...")
                    return await self._generate_openai(prompt)
                raise

        if self._openai_key:
            logger.info("Gemini/Groq keys not set. Generating via OpenAI API...")
            return await self._generate_openai(prompt)

        raise RuntimeError(
            "No valid LLM API key provided. Please configure GEMINI_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY in your .env file."
        )

    async def _generate_gemini(self, prompt: str) -> str:
        """Call Gemini REST API with retry logic."""
        if not self._gemini_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini provider.")

        url = f"{GEMINI_API_URL}/{self._gemini_model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096,
            },
        }

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.post(
                    url,
                    params={"key": self._gemini_key},
                    json=payload,
                )

                if response.status_code in (429, 503) and attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning("Gemini status %d. Retrying in %ds...", response.status_code, wait_time)
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError("Gemini returned no response candidates.")

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise RuntimeError("Gemini returned empty response content.")

                return parts[0].get("text", "")

            except httpx.HTTPStatusError as err:
                status = err.response.status_code
                if status == 429:
                    raise RuntimeError("Gemini API rate limit exceeded (429 Too Many Requests).") from err
                if status in (400, 403):
                    raise RuntimeError("Gemini API authentication failed. Verify GEMINI_API_KEY.") from err
                raise RuntimeError(f"Gemini API HTTP Error {status}: {err.response.text}") from err

            except httpx.RequestError as err:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                    continue
                raise RuntimeError(f"Network error communicating with Gemini API: {err}") from err

        raise RuntimeError("Gemini API request failed after retries.")

    async def _generate_groq(self, prompt: str) -> str:
        """Call Groq OpenAI-compatible REST API with retry logic."""
        if not self._groq_key:
            raise ValueError("GROQ_API_KEY is required for Groq provider.")

        headers = {
            "Authorization": f"Bearer {self._groq_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 4096,
        }

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.post(
                    GROQ_API_URL,
                    headers=headers,
                    json=payload,
                )

                if response.status_code in (429, 503) and attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning("Groq status %d. Retrying in %ds...", response.status_code, wait_time)
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError("Groq returned no response choices.")

                message = choices[0].get("message", {})
                content = message.get("content", "")
                if not content:
                    raise RuntimeError("Groq returned empty response text.")

                return content

            except httpx.HTTPStatusError as err:
                status = err.response.status_code
                if status == 429:
                    raise RuntimeError("Groq API rate limit exceeded (429 Too Many Requests).") from err
                if status in (400, 401, 403):
                    raise RuntimeError("Groq API authentication failed. Verify GROQ_API_KEY.") from err
                raise RuntimeError(f"Groq API HTTP Error {status}: {err.response.text}") from err

            except httpx.RequestError as err:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                    continue
                raise RuntimeError(f"Network error communicating with Groq API: {err}") from err

        raise RuntimeError("Groq API request failed after retries.")

    async def _generate_openai(self, prompt: str) -> str:
        """Call OpenAI REST API with retry logic."""
        if not self._openai_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider.")

        headers = {
            "Authorization": f"Bearer {self._openai_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._openai_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 4096,
        }

        for attempt in range(MAX_RETRIES):
            try:
                response = await self._client.post(
                    OPENAI_API_URL,
                    headers=headers,
                    json=payload,
                )

                if response.status_code in (429, 503) and attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning("OpenAI status %d. Retrying in %ds...", response.status_code, wait_time)
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError("OpenAI returned no response choices.")

                message = choices[0].get("message", {})
                content = message.get("content", "")
                if not content:
                    raise RuntimeError("OpenAI returned empty response text.")

                return content

            except httpx.HTTPStatusError as err:
                status = err.response.status_code
                if status == 429:
                    raise RuntimeError("OpenAI API rate limit exceeded (429 Too Many Requests).") from err
                if status in (400, 401, 403):
                    raise RuntimeError("OpenAI API authentication failed. Verify OPENAI_API_KEY.") from err
                raise RuntimeError(f"OpenAI API HTTP Error {status}: {err.response.text}") from err

            except httpx.RequestError as err:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2)
                    continue
                raise RuntimeError(f"Network error communicating with OpenAI API: {err}") from err

        raise RuntimeError("OpenAI API request failed after retries.")

    async def close(self) -> None:
        await self._client.aclose()
