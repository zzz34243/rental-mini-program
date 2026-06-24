from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    storage_dir: Path
    reviews_file: Path
    listings_file: Path
    favorites_file: Path
    ai_history_file: Path
    collection_runs_file: Path
    host: str
    port: int
    server_mode: str
    embedding_provider: str
    embedding_model: str
    ollama_base_url: str
    ollama_timeout_seconds: int
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_timeout_seconds: int


def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parent.parent
    storage_dir = base_dir / "storage"

    return Settings(
        base_dir=base_dir,
        storage_dir=storage_dir,
        reviews_file=storage_dir / "reviews.json",
        listings_file=storage_dir / "listings.json",
        favorites_file=storage_dir / "favorites.json",
        ai_history_file=storage_dir / "ai_history.json",
        collection_runs_file=storage_dir / "collection_runs.json",
        host=os.environ.get("ANJU_HOST", "0.0.0.0"),
        port=int(os.environ.get("ANJU_PORT", "5000")),
        server_mode=os.environ.get("ANJU_SERVER_MODE", "auto").strip().lower() or "auto",
        embedding_provider=os.environ.get("ANJU_EMBEDDING_PROVIDER", "auto").strip().lower() or "auto",
        embedding_model=os.environ.get("ANJU_EMBEDDING_MODEL", "embeddinggemma").strip() or "embeddinggemma",
        ollama_base_url=os.environ.get("ANJU_OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip().rstrip("/"),
        ollama_timeout_seconds=max(1, int(os.environ.get("ANJU_OLLAMA_TIMEOUT", "20"))),
        llm_base_url=os.environ.get("ANJU_LLM_BASE_URL", "").strip().rstrip("/"),
        llm_api_key=os.environ.get("ANJU_LLM_API_KEY", "").strip(),
        llm_model=os.environ.get("ANJU_LLM_MODEL", "").strip(),
        llm_timeout_seconds=max(1, int(os.environ.get("ANJU_LLM_TIMEOUT", "120"))),
    )
