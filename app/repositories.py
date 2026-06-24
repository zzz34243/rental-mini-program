from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable

from .models import AIHistoryRecord, CollectionRun, FavoriteRecord, House, Review


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(payload, list):
        return []

    return [item for item in payload if isinstance(item, dict)]


class JsonListRepository:
    def __init__(self, path: Path, seed_factory: Callable[[], list[dict[str, Any]]]):
        self.path = path
        self.seed_factory = seed_factory
        self.lock = threading.RLock()

    def ensure_exists(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            return
        self.write_all(self.seed_factory())

    def read_all(self) -> list[dict[str, Any]]:
        self.ensure_exists()
        with self.lock:
            data = _read_json_list(self.path)
            if data:
                return data
            seed = self.seed_factory()
            self.write_all(seed)
            return seed

    def write_all(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(items, ensure_ascii=False, indent=2)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with self.lock:
            temp_path.write_text(payload, encoding="utf-8")
            temp_path.replace(self.path)


class HouseRepository:
    def __init__(self, store: JsonListRepository):
        self.store = store

    def list_houses(
        self,
        *,
        category: str = "",
        keyword: str = "",
        city_name: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        items = self.store.read_all()
        filtered = []
        keyword_text = keyword.strip().lower()
        city_text = city_name.strip().lower()
        category_text = category.strip().lower()

        for item in items:
            if category_text and item.get("category", "").lower() != category_text:
                continue
            if city_text and item.get("cityName", "").lower() != city_text:
                continue
            if keyword_text:
                haystack = " ".join(
                    [
                        item.get("title", ""),
                        item.get("communityName", ""),
                        item.get("districtText", ""),
                        item.get("summary", ""),
                        item.get("searchText", ""),
                    ]
                ).lower()
                if keyword_text not in haystack:
                    continue
            filtered.append(item)

        total = len(filtered)
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        return filtered[start:end], total

    def get_house(self, house_id: str) -> dict[str, Any] | None:
        for item in self.store.read_all():
            if item.get("id") == house_id:
                return item
        return None

    def upsert_many(self, houses: list[House]) -> list[dict[str, Any]]:
        existing = self.store.read_all()
        by_id = {item.get("id"): item for item in existing}
        for house in houses:
            by_id[house.id] = house.to_dict()
        merged = list(by_id.values())
        self.store.write_all(merged)
        return merged

    def list_all(self) -> list[dict[str, Any]]:
        return self.store.read_all()

    def replace_all(self, houses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self.store.write_all(houses)
        return houses


class ReviewRepository:
    def __init__(self, store: JsonListRepository):
        self.store = store

    def list_reviews(
        self,
        *,
        house_title: str = "",
        limit: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        items = self.store.read_all()
        filtered = items

        if house_title:
            filtered = [item for item in filtered if item.get("houseTitle") == house_title]

        if limit is not None:
            filtered = filtered[:limit]
            return filtered, len(filtered)

        total = len(filtered)
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        return filtered[start:end], total

    def prepend(self, review: Review) -> list[dict[str, Any]]:
        items = [item for item in self.store.read_all() if item.get("id") != review.id]
        next_items = [review.to_dict(), *items]
        self.store.write_all(next_items)
        return next_items


class AIHistoryRepository:
    def __init__(self, store: JsonListRepository):
        self.store = store

    def list_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.store.read_all()[:limit]

    def prepend(self, record: AIHistoryRecord) -> list[dict[str, Any]]:
        items = [item for item in self.store.read_all() if item.get("id") != record.id]
        next_items = [record.to_dict(), *items]
        self.store.write_all(next_items[:100])
        return next_items


class FavoriteRepository:
    def __init__(self, store: JsonListRepository):
        self.store = store

    def list_favorite_records(self) -> list[dict[str, Any]]:
        return self.store.read_all()

    def list_favorite_ids(self) -> list[str]:
        return [
            str(item.get("houseId", "")).strip()
            for item in self.store.read_all()
            if str(item.get("houseId", "")).strip()
        ]

    def add(self, favorite: FavoriteRecord) -> list[dict[str, Any]]:
        items = [
            item
            for item in self.store.read_all()
            if item.get("houseId") != favorite.houseId
        ]
        next_items = [favorite.to_dict(), *items]
        self.store.write_all(next_items[:200])
        return next_items

    def remove(self, house_id: str) -> tuple[list[dict[str, Any]], bool]:
        items = self.store.read_all()
        next_items = [item for item in items if item.get("houseId") != house_id]
        removed = len(next_items) != len(items)
        if removed:
            self.store.write_all(next_items)
        return next_items, removed


class CollectionRunRepository:
    def __init__(self, store: JsonListRepository):
        self.store = store

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.store.read_all()[:limit]

    def prepend(self, run: CollectionRun) -> list[dict[str, Any]]:
        items = [item for item in self.store.read_all() if item.get("id") != run.id]
        next_items = [run.to_dict(), *items]
        self.store.write_all(next_items[:100])
        return next_items
