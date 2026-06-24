from __future__ import annotations

from uuid import uuid4

from .answer_generator import AnswerGenerator
from .collectors import CollectorRegistry
from .config import Settings
from .demand_parser import DemandParser
from .embeddings import EmbeddingService
from .llm_client import LLMClient
from .models import AIHistoryRecord, CollectionRun, FavoriteRecord, Review
from .normalizers import build_embedding_text, normalize_listing
from .repositories import (
    AIHistoryRepository,
    CollectionRunRepository,
    FavoriteRepository,
    HouseRepository,
    JsonListRepository,
    ReviewRepository,
)
from .sample_data import DEFAULT_HOUSES, DEFAULT_REVIEWS
from .serializers import serialize_house, serialize_house_list
from .search import build_recommendation


def _house_seed() -> list[dict]:
    return [item.to_dict() for item in DEFAULT_HOUSES]


def _review_seed() -> list[dict]:
    return [item.to_dict() for item in DEFAULT_REVIEWS]


def _empty_seed() -> list[dict]:
    return []


class ServiceContainer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.house_repository = HouseRepository(
            JsonListRepository(settings.listings_file, _house_seed)
        )
        self.review_repository = ReviewRepository(
            JsonListRepository(settings.reviews_file, _review_seed)
        )
        self.favorite_repository = FavoriteRepository(
            JsonListRepository(settings.favorites_file, _empty_seed)
        )
        self.ai_history_repository = AIHistoryRepository(
            JsonListRepository(settings.ai_history_file, _empty_seed)
        )
        self.collection_run_repository = CollectionRunRepository(
            JsonListRepository(settings.collection_runs_file, _empty_seed)
        )
        self.collector_registry = CollectorRegistry()
        self.embedding_service = EmbeddingService(settings)
        self.llm_client = LLMClient(settings)
        self.demand_parser = DemandParser(self.llm_client)
        self.answer_generator = AnswerGenerator(self.llm_client)

    def health_payload(self) -> dict:
        houses = self.house_repository.list_all()
        embedded_count = sum(1 for item in houses if item.get("embeddingVector"))
        embedding_status = self.embedding_service.get_status()
        llm_status = self.llm_client.get_status()
        return {
            "ok": True,
            "service": "anju-housing-service",
            "storageReady": True,
            "sources": self.collector_registry.list_sources(),
            "embeddingProvider": embedding_status.effective_provider,
            "embeddingModel": embedding_status.effective_model,
            "embeddingStatus": embedding_status.to_dict(),
            "llmStatus": llm_status.to_dict(),
            "embeddedHouseCount": embedded_count,
            "houseCount": len(houses),
            "favoriteCount": len(self.favorite_repository.list_favorite_ids()),
        }

    def get_houses(
        self,
        *,
        category: str = "",
        keyword: str = "",
        city_name: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        house_list, total = self.house_repository.list_houses(
            category=category,
            keyword=keyword,
            city_name=city_name,
            page=page,
            page_size=page_size,
        )
        return {
            "ok": True,
            "houseList": serialize_house_list(house_list),
            "total": total,
            "page": page,
            "pageSize": page_size,
        }

    def get_house_detail(self, house_id: str) -> dict | None:
        house = self.house_repository.get_house(house_id)
        if not house:
            return None
        return {"ok": True, "house": serialize_house(house)}

    def get_reviews(
        self,
        *,
        house_title: str = "",
        limit: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        review_list, total = self.review_repository.list_reviews(
            house_title=house_title,
            limit=limit,
            page=page,
            page_size=page_size,
        )
        return {
            "ok": True,
            "reviewList": review_list,
            "total": total,
            "page": page,
            "pageSize": page_size,
        }

    def create_review(self, payload: dict) -> dict:
        house_title = str(payload.get("houseTitle", "")).strip()
        community_name = str(payload.get("communityName", "")).strip()
        content = str(payload.get("content", "")).strip()

        try:
            score = int(payload.get("score", 0))
        except (TypeError, ValueError):
            score = 0

        if not house_title or not community_name or not content or score < 1 or score > 5:
            raise ValueError("房源名称、小区名称、评分和评价内容不能为空")

        living_tags = payload.get("livingTags", [])
        if not isinstance(living_tags, list):
            living_tags = []

        display_name = "匿名用户" if payload.get("isAnonymous") else str(
            payload.get("displayName", "")
        ).strip()
        display_name = display_name or "匿名用户"

        review = Review(
            id=str(payload.get("id") or f"review-{uuid4().hex[:12]}"),
            houseTitle=house_title,
            communityName=community_name,
            score=score,
            livingTags=[str(tag).strip() for tag in living_tags if str(tag).strip()],
            content=content,
            displayName=display_name,
        )
        review_list = self.review_repository.prepend(review)
        return {
            "ok": True,
            "review": review.to_dict(),
            "reviewList": review_list,
            "total": len(review_list),
        }

    def recommend(self, payload: dict) -> dict:
        query = str(payload.get("query", "")).strip()
        city_name = str(payload.get("cityName", "")).strip()

        if not query:
            raise ValueError("query 不能为空")

        demand_result = self.demand_parser.parse(query=query, city_name=city_name)
        demand = demand_result["demand"]
        houses = self.house_repository.list_all()
        recommendation = build_recommendation(
            query=query,
            houses=houses,
            embedding_service=self.embedding_service,
            city_name=city_name,
            demand=demand,
        )
        serialized_recommend_list = serialize_house_list(
            recommendation.get("recommendList", [])
        )
        answer_result = self.answer_generator.generate(
            query=query,
            summary=recommendation.get("summary", ""),
            demand=demand,
            recommend_list=serialized_recommend_list,
        )
        demand_parse_source = demand_result["source"]
        match_strategy_prefix = "llm-parse" if demand_parse_source == "llm" else "rule-parse"
        degraded = bool(demand_result["degraded"] or answer_result["degraded"])
        llm_used = bool(demand_result["llmUsed"] or answer_result["llmUsed"])
        mode = "hybrid" if llm_used and not degraded else "degraded" if degraded else "local"

        recommendation["recommendList"] = serialized_recommend_list
        recommendation["matchStrategy"] = f"{match_strategy_prefix} + embedding-hybrid-ranking"
        return {
            "ok": True,
            **recommendation,
            "demand": demand,
            "answer": answer_result["text"],
            "mode": mode,
            "llmUsed": llm_used,
            "degraded": degraded,
            "demandParseSource": demand_parse_source,
            "answerSource": answer_result["source"],
            "parseMessage": demand_result["message"],
            "answerMessage": answer_result["message"],
        }

    def list_ai_history(self, limit: int = 20) -> dict:
        history_list = self.ai_history_repository.list_history(limit=limit)
        return {"ok": True, "historyList": history_list, "total": len(history_list)}

    def save_ai_history(self, payload: dict) -> dict:
        user_text = str(payload.get("userText", "")).strip()
        summary = str(payload.get("summary", "")).strip()
        intent_label = str(payload.get("intentLabel", "")).strip()
        demand_tags = payload.get("demandTags", [])
        recommend_ids = payload.get("recommendIds", [])

        if not user_text or not summary or not intent_label:
            raise ValueError("userText、summary、intentLabel 不能为空")

        record = AIHistoryRecord(
            id=str(payload.get("id") or f"ai-history-{uuid4().hex[:12]}"),
            userText=user_text,
            summary=summary,
            demandTags=[str(tag).strip() for tag in demand_tags if str(tag).strip()],
            intentLabel=intent_label,
            recommendIds=[str(item).strip() for item in recommend_ids if str(item).strip()],
        )
        history_list = self.ai_history_repository.prepend(record)
        return {"ok": True, "record": record.to_dict(), "historyList": history_list}

    def run_collection(self, payload: dict) -> dict:
        city_name = str(payload.get("cityName", "")).strip() or "北京"
        category = str(payload.get("category", "")).strip() or "all"
        source_names = payload.get("sources", [])
        if not isinstance(source_names, list):
            source_names = []
        source_names = [str(item).strip() for item in source_names if str(item).strip()]

        raw_items, collect_errors = self.collector_registry.collect(
            city_name=city_name,
            category=category,
            source_names=source_names,
        )
        normalized_items = [normalize_listing(item) for item in raw_items]
        merged = self.house_repository.upsert_many(normalized_items)

        status = "completed" if normalized_items else "partial"
        message_parts = []
        if normalized_items:
            message_parts.append("已完成采集、规范化和入库。")
        if collect_errors:
            message_parts.append("部分数据源失败：" + " | ".join(collect_errors))
        if not message_parts:
            message_parts.append("本次未采集到新房源。")

        run = CollectionRun(
            id=f"collect-{uuid4().hex[:12]}",
            sources=source_names or self.collector_registry.list_sources(),
            cityName=city_name,
            category=category,
            status=status,
            collectedCount=len(normalized_items),
            message=" ".join(message_parts),
        )
        self.collection_run_repository.prepend(run)
        return {
            "ok": True,
            "run": run.to_dict(),
            "houseCount": len(merged),
            "ingestedCount": len(normalized_items),
            "errors": collect_errors,
        }

    def rebuild_embeddings(self, payload: dict) -> dict:
        force = bool(payload.get("force", False))
        source_names = payload.get("sources", [])
        if not isinstance(source_names, list):
            source_names = []
        source_names = {str(item).strip() for item in source_names if str(item).strip()}
        embedding_status = self.embedding_service.get_status()

        if (
            self.settings.embedding_provider == "ollama"
            and (
                not embedding_status.ollama_reachable
                or not embedding_status.ollama_model_available
            )
        ):
            raise ValueError(embedding_status.message)

        houses = self.house_repository.list_all()
        updated_houses = []
        embedded_count = 0

        for house in houses:
            current_source = str(house.get("sourceName", "")).strip()
            if source_names and current_source not in source_names:
                updated_houses.append(house)
                continue

            if house.get("embeddingVector") and not force:
                updated_houses.append(house)
                continue

            next_house = dict(house)
            next_house["embeddingText"] = build_embedding_text(next_house)
            embedding = self.embedding_service.embed_house(next_house)
            next_house["embeddingModel"] = embedding.model
            next_house["embeddingVector"] = embedding.vector
            updated_houses.append(next_house)
            embedded_count += 1

        self.house_repository.replace_all(updated_houses)
        return {
            "ok": True,
            "embeddedCount": embedded_count,
            "houseCount": len(updated_houses),
            "embeddingProvider": embedding_status.effective_provider,
            "embeddingModel": embedding_status.effective_model,
            "embeddingStatus": embedding_status.to_dict(),
            "force": force,
        }

    def list_collection_runs(self, limit: int = 20) -> dict:
        runs = self.collection_run_repository.list_runs(limit=limit)
        return {"ok": True, "runList": runs, "total": len(runs)}

    def list_favorites(self) -> dict:
        favorite_ids = self.favorite_repository.list_favorite_ids()
        favorite_list = []

        for house_id in favorite_ids:
            house = self.house_repository.get_house(house_id)
            if not house:
                continue

            favorite_house = serialize_house(house)
            favorite_house["isFavorite"] = True
            favorite_list.append(favorite_house)

        return {
            "ok": True,
            "favoriteList": favorite_list,
            "favoriteIds": [item["id"] for item in favorite_list],
            "total": len(favorite_list),
        }

    def add_favorite(self, payload: dict) -> dict:
        house_id = str(payload.get("houseId", "")).strip()
        if not house_id:
            raise ValueError("houseId 不能为空")

        house = self.house_repository.get_house(house_id)
        if not house:
            raise ValueError("房源不存在")

        favorite = FavoriteRecord(houseId=house_id)
        self.favorite_repository.add(favorite)
        favorite_house = serialize_house(house)
        favorite_house["isFavorite"] = True

        return {
            "ok": True,
            "favorite": favorite.to_dict(),
            "house": favorite_house,
            "favoriteId": house_id,
        }

    def remove_favorite(self, house_id: str) -> dict:
        normalized_house_id = str(house_id).strip()
        if not normalized_house_id:
            raise ValueError("houseId 不能为空")

        _, removed = self.favorite_repository.remove(normalized_house_id)
        if not removed:
            raise ValueError("收藏记录不存在")

        return {
            "ok": True,
            "houseId": normalized_house_id,
            "removed": True,
        }
