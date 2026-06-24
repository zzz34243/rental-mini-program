from __future__ import annotations

import re
from typing import Any

from .embeddings import EmbeddingService, cosine_similarity


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_PATTERN.finditer(text or "")}


def infer_intent(query: str) -> str:
    if any(keyword in query for keyword in ("买", "购房", "总价", "首付", "置业")):
        return "买房"
    return "租房"


def extract_demand_tags(query: str) -> list[str]:
    rules = [
        ("近地铁", ("地铁", "通勤")),
        ("学区优先", ("学区", "学校")),
        ("医疗配套", ("医院", "医疗")),
        ("安静", ("安静", "隔音")),
        ("可做饭", ("做饭", "厨房")),
        ("预算友好", ("预算", "便宜", "总价可控")),
        ("采光好", ("采光", "朝南", "通透")),
        ("适合家庭", ("家庭", "孩子", "老人")),
    ]
    tags = [label for label, keywords in rules if any(keyword in query for keyword in keywords)]
    if not tags:
        tags.append("个性化匹配")
    return tags


def summarize_query(intent_label: str, demand_tags: list[str], budget: dict[str, Any] | None = None) -> str:
    tag_text = "、".join(demand_tags or ["个性化匹配"])
    budget = budget or {}
    budget_max = budget.get("max")
    budget_unit = budget.get("unit", "")
    if budget_max is not None:
        return f"已完成{intent_label}需求解析，预算控制在{budget_max:g}{budget_unit}以内，优先考虑{tag_text}相关房源。"
    return f"已完成{intent_label}需求解析，优先考虑{tag_text}相关房源。"


def _house_text_for_matching(house: dict[str, Any]) -> str:
    return " ".join(
        [
            house.get("title", ""),
            house.get("communityName", ""),
            house.get("districtText", ""),
            house.get("summary", ""),
            house.get("trafficText", ""),
            house.get("lifestyleText", ""),
            house.get("searchText", ""),
            house.get("embeddingText", ""),
            " ".join(house.get("tags", [])),
        ]
    )


def _parse_house_price_value(house: dict[str, Any], intent_label: str) -> float | None:
    price_text = str(house.get("priceText", "")).strip().lower()
    if not price_text:
        return None

    match = re.search(r"(\d+(?:\.\d+)?)", price_text)
    if not match:
        return None

    try:
        value = float(match.group(1))
    except (TypeError, ValueError):
        return None

    if intent_label == "租房":
        if "万" in price_text and "元" not in price_text:
            return value * 10000
        return value

    if "亿" in price_text:
        return value * 10000
    return value


def _matches_budget(house: dict[str, Any], budget: dict[str, Any], intent_label: str) -> bool:
    budget_max = budget.get("max")
    if budget_max is None:
        return True

    house_price = _parse_house_price_value(house, intent_label)
    if house_price is None:
        return True

    return house_price <= float(budget_max) * 1.15


def _matches_tags(house: dict[str, Any], required_tags: list[str]) -> bool:
    if not required_tags:
        return True

    house_tags = {str(tag).strip() for tag in house.get("tags", []) if str(tag).strip()}
    return all(tag in house_tags for tag in required_tags)


def filter_houses_by_demand(houses: list[dict[str, Any]], demand: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    active_houses = [house for house in houses if house.get("isActive", True)]
    intent_label = str(demand.get("intentLabel", "")).strip() or "租房"
    city_name = str(demand.get("cityName", "")).strip()
    budget = demand.get("budget", {})
    must_have_tags = demand.get("mustHaveTags", [])

    def matches_core(house: dict[str, Any]) -> bool:
        if intent_label and house.get("intentLabel") != intent_label:
            return False
        if city_name and house.get("cityName") != city_name:
            return False
        if not _matches_budget(house, budget, intent_label):
            return False
        return True

    strict = [house for house in active_houses if matches_core(house) and _matches_tags(house, must_have_tags)]
    if strict:
        return strict, False

    relaxed = [house for house in active_houses if matches_core(house)]
    if relaxed:
        return relaxed, bool(must_have_tags)

    return active_houses, True


def score_house_lexically(query: str, house: dict[str, Any], *, demand: dict[str, Any]) -> float:
    score = 0.0
    query_text = " ".join(
        [
            query,
            " ".join(demand.get("keywords", [])),
            " ".join(demand.get("demandTags", [])),
        ]
    )
    query_tokens = tokenize(query_text)
    house_tokens = tokenize(_house_text_for_matching(house))

    score += len(query_tokens & house_tokens) * 4

    intent_label = str(demand.get("intentLabel", "")).strip()
    city_name = str(demand.get("cityName", "")).strip()
    if intent_label and intent_label == house.get("intentLabel"):
        score += 12
    if city_name and city_name == house.get("cityName"):
        score += 6

    house_tags = {str(tag).strip() for tag in house.get("tags", []) if str(tag).strip()}
    for tag in demand.get("mustHaveTags", []):
        if tag in house_tags:
            score += 8
    for tag in demand.get("preferredTags", []):
        if tag in house_tags:
            score += 5

    if _matches_budget(house, demand.get("budget", {}), intent_label or infer_intent(query)):
        score += 4

    return score


def score_house_semantically(query_vector: list[float], house: dict[str, Any]) -> float:
    house_vector = house.get("embeddingVector", [])
    if not isinstance(house_vector, list):
        return 0.0
    cleaned = [float(item) for item in house_vector if isinstance(item, (int, float))]
    if not cleaned:
        return 0.0
    return cosine_similarity(query_vector, cleaned)


def _build_query_embedding_text(query: str, demand: dict[str, Any]) -> str:
    parts = [
        query,
        str(demand.get("intentLabel", "")).strip(),
        str(demand.get("cityName", "")).strip(),
        " ".join(demand.get("mustHaveTags", [])),
        " ".join(demand.get("preferredTags", [])),
        " ".join(demand.get("keywords", [])),
        str(demand.get("budget", {}).get("raw", "")).strip(),
    ]
    return " ".join(part for part in parts if part).strip()


def build_recommendation(
    *,
    query: str,
    houses: list[dict[str, Any]],
    embedding_service: EmbeddingService,
    city_name: str = "",
    limit: int = 10,
    demand: dict[str, Any] | None = None,
) -> dict[str, Any]:
    demand = demand or {
        "rawQuery": query,
        "intentLabel": infer_intent(query),
        "cityName": city_name,
        "budget": {"max": None, "unit": "", "raw": ""},
        "mustHaveTags": [],
        "preferredTags": extract_demand_tags(query),
        "demandTags": extract_demand_tags(query),
        "keywords": [],
        "parseSource": "rule",
    }
    filtered_houses, filter_relaxed = filter_houses_by_demand(houses, demand)
    query_embedding = embedding_service.embed_text(_build_query_embedding_text(query, demand))
    semantic_weight = 10 if query_embedding.provider == "hash" else 100
    scored = []

    for house in filtered_houses:
        lexical_score = score_house_lexically(query, house, demand=demand)
        semantic_score = score_house_semantically(query_embedding.vector, house)
        hybrid_score = lexical_score + semantic_score * semantic_weight
        scored.append(
            {
                "house": house,
                "hybridScore": hybrid_score,
                "semanticScore": round(semantic_score, 4),
                "lexicalScore": round(lexical_score, 2),
            }
        )

    scored.sort(key=lambda item: item["hybridScore"], reverse=True)
    recommend_list = []
    for item in scored[:limit]:
        house = dict(item["house"])
        house["matchMeta"] = {
            "hybridScore": round(item["hybridScore"], 4),
            "semanticScore": item["semanticScore"],
            "lexicalScore": item["lexicalScore"],
            "embeddingModel": house.get("embeddingModel", ""),
        }
        recommend_list.append(house)

    return {
        "intentLabel": demand.get("intentLabel", infer_intent(query)),
        "demandTags": demand.get("demandTags", extract_demand_tags(query)),
        "summary": summarize_query(
            demand.get("intentLabel", infer_intent(query)),
            demand.get("demandTags", extract_demand_tags(query)),
            demand.get("budget", {}),
        ),
        "recommendList": recommend_list,
        "matchStrategy": "embedding-hybrid-ranking",
        "embeddingProvider": query_embedding.provider,
        "embeddingModel": query_embedding.model,
        "filteredHouseCount": len(filtered_houses),
        "filterRelaxed": filter_relaxed,
    }
