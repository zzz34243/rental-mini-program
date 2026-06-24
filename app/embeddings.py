from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import Settings


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


@dataclass(slots=True)
class EmbeddingResult:
    vector: list[float]
    model: str
    provider: str


@dataclass(slots=True)
class EmbeddingStatus:
    configured_provider: str
    configured_model: str
    effective_provider: str
    effective_model: str
    ollama_enabled: bool
    ollama_reachable: bool
    ollama_model_available: bool
    fallback_active: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "configuredProvider": self.configured_provider,
            "configuredModel": self.configured_model,
            "effectiveProvider": self.effective_provider,
            "effectiveModel": self.effective_model,
            "ollamaEnabled": self.ollama_enabled,
            "ollamaReachable": self.ollama_reachable,
            "ollamaModelAvailable": self.ollama_model_available,
            "fallbackActive": self.fallback_active,
            "message": self.message,
        }


class HashEmbeddingProvider:
    provider_name = "hash"
    model_name = "hash-embedding-v1"
    dimensions = 96

    def embed(self, text: str) -> EmbeddingResult:
        vector = [0.0] * self.dimensions
        tokens = [token for token in text.split() if token]
        if not tokens:
            return EmbeddingResult(vector=vector, model=self.model_name, provider=self.provider_name)

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = digest[0] % self.dimensions
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            weight = 1.0 + (digest[2] / 255.0)
            vector[bucket] += sign * weight

        norm = math.sqrt(sum(item * item for item in vector))
        if norm:
            vector = [item / norm for item in vector]

        return EmbeddingResult(vector=vector, model=self.model_name, provider=self.provider_name)


class OllamaEmbeddingProvider:
    provider_name = "ollama"

    def __init__(self, settings: Settings):
        self.base_url = settings.ollama_base_url
        self.model_name = settings.embedding_model
        self.timeout_seconds = settings.ollama_timeout_seconds

    def embed(self, text: str) -> EmbeddingResult:
        request_body = json.dumps(
            {
                "model": self.model_name,
                "input": text,
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/embed",
            data=request_body,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 404:
                return self._embed_legacy(text)
            raise RuntimeError(f"ollama embed failed: HTTP {error.code}") from error
        except URLError as error:
            raise RuntimeError(f"ollama embed failed: {error}") from error

        vectors = payload.get("embeddings", [])
        if not isinstance(vectors, list) or not vectors:
            raise RuntimeError("ollama embed failed: empty embeddings")

        vector = vectors[0]
        if not isinstance(vector, list):
            raise RuntimeError("ollama embed failed: invalid embedding payload")

        return EmbeddingResult(
            vector=[float(item) for item in vector if isinstance(item, (int, float))],
            model=self.model_name,
            provider=self.provider_name,
        )

    def _embed_legacy(self, text: str) -> EmbeddingResult:
        request_body = json.dumps(
            {
                "model": self.model_name,
                "prompt": text,
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/embeddings",
            data=request_body,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as error:
            raise RuntimeError(f"ollama legacy embeddings failed: {error}") from error

        vector = payload.get("embedding", [])
        if not isinstance(vector, list):
            raise RuntimeError("ollama legacy embeddings failed: invalid embedding payload")

        return EmbeddingResult(
            vector=[float(item) for item in vector if isinstance(item, (int, float))],
            model=self.model_name,
            provider=self.provider_name,
        )


class EmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.hash_provider = HashEmbeddingProvider()
        self.ollama_provider = OllamaEmbeddingProvider(settings)

    def get_status(self) -> EmbeddingStatus:
        configured_provider = self.settings.embedding_provider
        configured_model = self.settings.embedding_model

        if configured_provider == "hash":
            return EmbeddingStatus(
                configured_provider=configured_provider,
                configured_model=self.hash_provider.model_name,
                effective_provider=self.hash_provider.provider_name,
                effective_model=self.hash_provider.model_name,
                ollama_enabled=False,
                ollama_reachable=False,
                ollama_model_available=False,
                fallback_active=False,
                message="Embedding provider is pinned to hash.",
            )

        ollama_probe = self._probe_ollama()
        ollama_reachable = ollama_probe["reachable"]
        ollama_model_available = ollama_probe["model_available"]
        ollama_message = ollama_probe["message"]

        if configured_provider == "ollama":
            if ollama_reachable and ollama_model_available:
                return EmbeddingStatus(
                    configured_provider=configured_provider,
                    configured_model=configured_model,
                    effective_provider=self.ollama_provider.provider_name,
                    effective_model=configured_model,
                    ollama_enabled=True,
                    ollama_reachable=True,
                    ollama_model_available=True,
                    fallback_active=False,
                    message="Ollama embedding is ready.",
                )
            return EmbeddingStatus(
                configured_provider=configured_provider,
                configured_model=configured_model,
                effective_provider=self.ollama_provider.provider_name,
                effective_model=configured_model,
                ollama_enabled=True,
                ollama_reachable=ollama_reachable,
                ollama_model_available=ollama_model_available,
                fallback_active=False,
                message=ollama_message,
            )

        if ollama_reachable and ollama_model_available:
            return EmbeddingStatus(
                configured_provider=configured_provider,
                configured_model=configured_model,
                effective_provider=self.ollama_provider.provider_name,
                effective_model=configured_model,
                ollama_enabled=True,
                ollama_reachable=True,
                ollama_model_available=True,
                fallback_active=False,
                message="Auto mode is using Ollama embedding.",
            )

        return EmbeddingStatus(
            configured_provider=configured_provider,
            configured_model=configured_model,
            effective_provider=self.hash_provider.provider_name,
            effective_model=self.hash_provider.model_name,
            ollama_enabled=True,
            ollama_reachable=ollama_reachable,
            ollama_model_available=ollama_model_available,
            fallback_active=True,
            message=ollama_message or "Auto mode fell back to hash embedding.",
        )

    def get_provider_name(self) -> str:
        return self.get_status().effective_provider

    def get_model_name(self) -> str:
        return self.get_status().effective_model

    def embed_text(self, text: str) -> EmbeddingResult:
        provider = self.settings.embedding_provider

        if provider == "hash":
            return self.hash_provider.embed(text)

        if provider == "ollama":
            return self.ollama_provider.embed(text)

        try:
            return self.ollama_provider.embed(text)
        except RuntimeError:
            return self.hash_provider.embed(text)

    def embed_house(self, house: dict) -> EmbeddingResult:
        text = str(house.get("embeddingText") or house.get("searchText") or "").strip()
        return self.embed_text(text)

    def _probe_ollama(self) -> dict[str, Any]:
        request = Request(
            f"{self.settings.ollama_base_url}/api/tags",
            headers={
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.settings.ollama_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            return {
                "reachable": False,
                "model_available": False,
                "message": f"Ollama probe failed: HTTP {error.code}.",
            }
        except URLError as error:
            return {
                "reachable": False,
                "model_available": False,
                "message": f"Ollama probe failed: {error.reason}.",
            }

        models = payload.get("models", [])
        if not isinstance(models, list):
            return {
                "reachable": True,
                "model_available": False,
                "message": "Ollama probe failed: invalid model list payload.",
            }

        configured_name = self.settings.embedding_model.strip()
        configured_base_name = configured_name.split(":", 1)[0]
        model_names = {
            str(item.get("name", "")).strip()
            for item in models
            if isinstance(item, dict)
        }
        model_base_names = {
            name.split(":", 1)[0]
            for name in model_names
            if name
        }
        model_available = (
            configured_name in model_names
            or configured_base_name in model_base_names
        )
        if model_available:
            return {
                "reachable": True,
                "model_available": True,
                "message": "Ollama is reachable and the embedding model is installed.",
            }

        return {
            "reachable": True,
            "model_available": False,
            "message": (
                f"Ollama is reachable but model '{self.settings.embedding_model}' is not installed."
            ),
        }
