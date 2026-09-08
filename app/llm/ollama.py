import json
import logging
import time
from collections.abc import AsyncGenerator

import httpx

from app.config import settings


logger = logging.getLogger("curly")


class OllamaError(Exception):
    pass


class OllamaClient:

    def __init__(
        self,
        base_url: str,
        model: str,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model

        # Reuse one HTTP client instead of constructing one per request.
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=120.0,
                write=30.0,
                pool=10.0,
            )
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def generate(
        self,
        messages: list[dict[str, str]],
        response_format: dict | None = None,
    ) -> str:

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "temperature": settings.llm_temperature,
                "num_predict": settings.llm_max_tokens,
            },
        }

        if response_format is not None:
            payload["format"] = response_format

        start = time.perf_counter()

        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )

            response.raise_for_status()

            elapsed_ms = (
                time.perf_counter() - start
            ) * 1000

            logger.info(
                "Ollama generation: %.2f ms",
                elapsed_ms,
            )

            data = response.json()

        except httpx.HTTPError as error:
            raise OllamaError(
                f"Ollama request failed: {error}"
            ) from error

        try:
            return data["message"]["content"]

        except (KeyError, TypeError) as error:
            raise OllamaError(
                f"Invalid Ollama response: {data}"
            ) from error

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "keep_alive": "10m",
            "options": {
                "temperature": settings.llm_temperature,
                "num_predict": settings.llm_max_tokens,
            },
        }

        started = time.perf_counter()
        first_token_time = None

        try:

            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:

                response.raise_for_status()

                async for line in response.aiter_lines():

                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    message = data.get("message") or {}
                    token = message.get("content", "")

                    if token and first_token_time is None:
                        first_token_time = (
                            time.perf_counter()
                            - started
                        )

                        logger.info(
                            "Ollama first token: %.2f ms",
                            first_token_time * 1000,
                        )

                    if token:
                        yield token

                    if data.get("done"):
                        break

                elapsed_ms = (
                    time.perf_counter() - started
                ) * 1000

                logger.info(
                    "Ollama streamed generation: %.2f ms",
                    elapsed_ms,
                )

        except httpx.HTTPError as error:
            raise OllamaError(
                f"Ollama streaming request failed: {error}"
            ) from error

    async def health(self) -> bool:

        try:

            response = await self.client.get(
                f"{self.base_url}/api/tags"
            )

            return response.status_code == 200

        except httpx.HTTPError:
            return False