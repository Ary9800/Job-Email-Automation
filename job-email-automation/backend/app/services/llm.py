import base64
import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    pass


class OllamaService:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.vision_model = settings.ollama_vision_model
        self.text_model = settings.ollama_text_model
        self.timeout = settings.ollama_timeout

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception as exc:
            logger.debug("Ollama not reachable: %s", exc)
            return False

    def list_models(self) -> list[str]:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            return [m["name"] for m in response.json().get("models", [])]
        except Exception:
            return []

    def has_model(self, model: str) -> bool:
        models = self.list_models()
        return any(model in name or name.startswith(f"{model}:") for name in models)

    def chat(self, prompt: str, model: str | None = None) -> str:
        model = model or self.text_model
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.7},
        }
        return self._post_chat(payload)

    def chat_with_image(self, prompt: str, image_path: Path, model: str | None = None) -> str:
        model = model or self.vision_model
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64],
                }
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }
        return self._post_chat(payload)

    def _post_chat(self, payload: dict) -> str:
        if not self.is_available():
            raise OllamaError(
                "Ollama is not running. Install from https://ollama.com and run: ollama serve"
            )

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "")
            if not content:
                raise OllamaError("Ollama returned an empty response")
            return content.strip()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            if exc.response.status_code == 404:
                model = payload.get("model", "unknown")
                raise OllamaError(
                    f"Model '{model}' not found. Run: ollama pull {model}"
                ) from exc
            raise OllamaError(f"Ollama request failed: {detail}") from exc
        except httpx.TimeoutException as exc:
            raise OllamaError(
                "Ollama timed out. Try a smaller vision model or a simpler screenshot."
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaError(f"Cannot reach Ollama at {self.base_url}: {exc}") from exc


ollama = OllamaService()
