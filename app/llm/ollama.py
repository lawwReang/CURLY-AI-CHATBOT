import httpx
from app.config import settings
import time
import logging

class OllamaError(Exception):
    pass


class OllamaClient:

    def __init__(
        self,
        base_url: str,
        model: str
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(
        self,
        messages: list[dict[str, str]],
        response_format: dict | None = None,
        start = time.perf_counter()
    ) -> str:

        payload = {
          "model": self.model,
          "messages": messages,
          "stream": False,
          "keep_alive": "10m",
          "options": {
               "temperature": settings.llm_temperature,
               "num_predict": settings.llm_max_tokens
          }
     }

        if response_format is not None:
            payload["format"] = response_format

        try:
            
            start = time.perf_counter()

            async with httpx.AsyncClient(
                timeout=120
            ) as client:

                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                )

                response.raise_for_status()

                elapsed_ms = (
                    time.perf_counter() - start
                ) * 1000

                logging.getLogger("curly").info(
                    "Ollama generation: %.2f ms",
                    elapsed_ms
                )

                data = response.json()

        except httpx.HTTPError as error:

            raise OllamaError(
                f"Ollama request failed: {error}"
            ) from error

        try:

            return data["message"]["content"]

        except KeyError as error:

            raise OllamaError(
                f"Invalid Ollama response: {data}"
            ) from error

    async def health(self) -> bool:

        try:

            async with httpx.AsyncClient(
                timeout=5
            ) as client:

                response = await client.get(
                    f"{self.base_url}/api/tags"
                )

                return response.status_code == 200

        except httpx.HTTPError:

            return False