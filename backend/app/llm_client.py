from __future__ import annotations

import json
import http.client
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .config import Settings


def _extract_json_object(text: str) -> dict[str, Any]:
    candidate = (text or "").strip()
    if not candidate:
        raise RuntimeError("llm returned empty content")

    if candidate.startswith("```"):
        for part in candidate.split("```"):
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            if cleaned.startswith("{") and cleaned.endswith("}"):
                candidate = cleaned
                break

    if not (candidate.startswith("{") and candidate.endswith("}")):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start:end + 1]

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as error:
        raise RuntimeError("llm returned invalid json content") from error

    if not isinstance(parsed, dict):
        raise RuntimeError("llm returned non-object json content")
    return parsed


@dataclass(slots=True)
class LLMStatus:
    configured: bool
    base_url: str
    model: str
    timeout_seconds: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "baseUrl": self.base_url,
            "model": self.model,
            "timeoutSeconds": self.timeout_seconds,
            "message": self.message,
        }


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def is_configured(self) -> bool:
        return bool(self.settings.llm_base_url and self.settings.llm_model)

    def get_status(self) -> LLMStatus:
        configured = self.is_configured()
        return LLMStatus(
            configured=configured,
            base_url=self.settings.llm_base_url,
            model=self.settings.llm_model,
            timeout_seconds=self.settings.llm_timeout_seconds,
            message=(
                "Cloud LLM is configured."
                if configured
                else "Cloud LLM is not configured; using local-only recommendation flow."
            ),
        )

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        payload = self.complete_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return _extract_json_object(payload)

    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        if not self.is_configured():
            raise RuntimeError("cloud llm is not configured")

        url = self.settings.llm_base_url
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"

        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }
        if response_format:
            body["response_format"] = response_format

        headers = {
            "Content-Type": "application/json",
        }
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        parsed_url = urlparse(url)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            raise RuntimeError("cloud llm request failed: invalid base url")

        path = parsed_url.path or "/"
        if parsed_url.query:
            path = f"{path}?{parsed_url.query}"

        connection_cls = (
            http.client.HTTPSConnection
            if parsed_url.scheme == "https"
            else http.client.HTTPConnection
        )
        request_body = json.dumps(body).encode("utf-8")
        last_error: OSError | None = None

        for attempt in range(3):
            connection = connection_cls(
                parsed_url.netloc,
                timeout=self.settings.llm_timeout_seconds,
            )
            try:
                connection.request(
                    "POST",
                    path,
                    body=request_body,
                    headers=headers,
                )
                response = connection.getresponse()
                raw_payload = response.read().decode("utf-8", errors="ignore")
                break
            except OSError as error:
                last_error = error
                if attempt == 2:
                    raise RuntimeError(f"cloud llm request failed: {error}") from error
                time.sleep(0.5 * (attempt + 1))
            finally:
                connection.close()
        else:  # pragma: no cover
            raise RuntimeError(f"cloud llm request failed: {last_error}")

        if response.status < 200 or response.status >= 300:
            raise RuntimeError(
                f"cloud llm request failed: HTTP {response.status} {raw_payload}".strip()
            )

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError as error:
            raise RuntimeError("cloud llm request failed: invalid response payload") from error

        choices = payload.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("cloud llm request failed: empty choices")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            text = "".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict)
            ).strip()
        else:
            text = str(content).strip()

        if not text:
            raise RuntimeError("cloud llm request failed: empty content")
        return text
