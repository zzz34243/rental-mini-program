from __future__ import annotations

import re
from typing import Any

from .llm_client import LLMClient


DEMAND_TAG_RULES = [
    ("近地铁", ("地铁", "通勤", "轨道交通")),
    ("学区优先", ("学区", "学校")),
    ("医疗配套", ("医院", "医疗")),
    ("安静", ("安静", "隔音")),
    ("可做饭", ("做饭", "厨房")),
    ("预算友好", ("预算", "便宜", "总价可控")),
    ("采光好", ("采光", "朝南", "通透")),
    ("适合家庭", ("家庭", "孩子", "老人")),
]
KNOWN_DEMAND_TAGS = [item[0] for item in DEMAND_TAG_RULES]
CHINESE_CITY_PATTERN = re.compile(r"(北京|上海|广州|深圳|杭州|成都|重庆|武汉|西安|南京|苏州|天津)")


def dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = str(item).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def infer_intent(query: str) -> str:
    if any(keyword in query for keyword in ("买", "购房", "总价", "首付", "置业")):
        return "买房"
    return "租房"


def extract_city(query: str, fallback_city_name: str = "") -> str:
    match = CHINESE_CITY_PATTERN.search(query or "")
    if match:
        return match.group(1)
    return fallback_city_name or "北京"


def extract_demand_tags(query: str) -> list[str]:
    tags = [label for label, keywords in DEMAND_TAG_RULES if any(keyword in query for keyword in keywords)]
    if not tags:
        tags.append("个性化匹配")
    return tags


def extract_keywords(query: str) -> list[str]:
    matches = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", query or "")
    return dedupe_strings(matches[:8])


def _parse_budget_number(fragment: str) -> float | None:
    try:
        return float(fragment)
    except (TypeError, ValueError):
        return None


def extract_budget(query: str, intent_label: str) -> dict[str, Any]:
    query_text = query or ""

    if intent_label == "买房":
        match = re.search(r"(\d+(?:\.\d+)?)\s*万", query_text)
        if match:
            value = _parse_budget_number(match.group(1))
            return {"max": value, "unit": "万元", "raw": match.group(0)} if value else {"max": None, "unit": "万元", "raw": ""}

        match = re.search(r"(预算|总价|首付)\s*(\d+(?:\.\d+)?)", query_text)
        if match:
            value = _parse_budget_number(match.group(2))
            return {"max": value, "unit": "万元", "raw": match.group(0)} if value else {"max": None, "unit": "万元", "raw": ""}

        return {"max": None, "unit": "万元", "raw": ""}

    match = re.search(r"(\d+(?:\.\d+)?)\s*(k|K|千)", query_text)
    if match:
        value = _parse_budget_number(match.group(1))
        return {"max": value * 1000, "unit": "元/月", "raw": match.group(0)} if value else {"max": None, "unit": "元/月", "raw": ""}

    match = re.search(r"(\d+(?:\.\d+)?)\s*(元|块)", query_text)
    if match:
        value = _parse_budget_number(match.group(1))
        return {"max": value, "unit": "元/月", "raw": match.group(0)} if value else {"max": None, "unit": "元/月", "raw": ""}

    match = re.search(r"(预算|月租|租金)\s*(\d+(?:\.\d+)?)", query_text)
    if match:
        value = _parse_budget_number(match.group(2))
        return {"max": value, "unit": "元/月", "raw": match.group(0)} if value else {"max": None, "unit": "元/月", "raw": ""}

    return {"max": None, "unit": "元/月", "raw": ""}


def build_rule_based_demand(query: str, city_name: str = "") -> dict[str, Any]:
    intent_label = infer_intent(query)
    demand_tags = extract_demand_tags(query)
    must_have_tags = [tag for tag in demand_tags if tag in ("近地铁", "学区优先", "医疗配套")]
    preferred_tags = [tag for tag in demand_tags if tag not in must_have_tags and tag != "个性化匹配"]
    return {
        "rawQuery": query,
        "intentLabel": intent_label,
        "cityName": extract_city(query, city_name),
        "budget": extract_budget(query, intent_label),
        "mustHaveTags": dedupe_strings(must_have_tags),
        "preferredTags": dedupe_strings(preferred_tags),
        "demandTags": dedupe_strings(demand_tags),
        "keywords": extract_keywords(query),
        "parseSource": "rule",
    }


def normalize_demand_payload(query: str, city_name: str, payload: dict[str, Any], source: str) -> dict[str, Any]:
    fallback = build_rule_based_demand(query, city_name)
    intent_label = str(payload.get("intentLabel", "")).strip()
    if intent_label not in ("买房", "租房"):
        intent_label = fallback["intentLabel"]

    parsed_city_name = str(payload.get("cityName", "")).strip() or fallback["cityName"]
    raw_budget = payload.get("budget", {})
    if not isinstance(raw_budget, dict):
        raw_budget = {}

    budget_max = raw_budget.get("max")
    try:
        budget_max = float(budget_max) if budget_max not in ("", None) else None
    except (TypeError, ValueError):
        budget_max = None

    budget_unit = str(raw_budget.get("unit", "")).strip() or fallback["budget"]["unit"]
    budget_raw = str(raw_budget.get("raw", "")).strip() or fallback["budget"]["raw"]
    budget = {
        "max": budget_max,
        "unit": budget_unit,
        "raw": budget_raw,
    }
    if budget["max"] is None and not budget["raw"]:
        budget = fallback["budget"]

    must_have_tags = [
        str(item).strip()
        for item in payload.get("mustHaveTags", [])
        if str(item).strip() in KNOWN_DEMAND_TAGS
    ]
    preferred_tags = [
        str(item).strip()
        for item in payload.get("preferredTags", [])
        if str(item).strip() in KNOWN_DEMAND_TAGS
    ]
    if not must_have_tags and not preferred_tags:
        preferred_tags = fallback["preferredTags"]
        must_have_tags = fallback["mustHaveTags"]

    demand_tags = dedupe_strings(
        must_have_tags
        + preferred_tags
        + [
            str(item).strip()
            for item in payload.get("demandTags", [])
            if str(item).strip() in KNOWN_DEMAND_TAGS or str(item).strip() == "个性化匹配"
        ]
    ) or fallback["demandTags"]
    keywords = dedupe_strings(
        [str(item).strip() for item in payload.get("keywords", []) if str(item).strip()]
    ) or fallback["keywords"]

    return {
        "rawQuery": query,
        "intentLabel": intent_label,
        "cityName": parsed_city_name,
        "budget": budget,
        "mustHaveTags": dedupe_strings(must_have_tags),
        "preferredTags": dedupe_strings(preferred_tags),
        "demandTags": demand_tags,
        "keywords": keywords,
        "parseSource": source,
    }


class DemandParser:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def parse(self, *, query: str, city_name: str = "") -> dict[str, Any]:
        fallback = build_rule_based_demand(query, city_name)
        if not self.llm_client.is_configured():
            return {
                "demand": fallback,
                "source": "rule",
                "llmUsed": False,
                "degraded": False,
                "message": "cloud llm is not configured",
            }

        system_prompt = (
            "你是房产需求解析器。"
            "只返回一个 JSON object，不要输出额外解释。"
            "字段必须包含 intentLabel、cityName、budget、mustHaveTags、preferredTags、demandTags、keywords。"
            "intentLabel 只能是 买房 或 租房。"
            f"demandTags 只能从这些标签里选择：{', '.join(KNOWN_DEMAND_TAGS)}。"
            "budget 必须是对象，格式为 {\"max\": number|null, \"unit\": string, \"raw\": string}。"
            "不要编造用户没有提到的硬性条件。"
        )
        user_prompt = (
            f"城市提示：{city_name or '北京'}\n"
            f"用户需求：{query}\n"
            "请返回 JSON。"
        )

        try:
            payload = self.llm_client.complete_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
            )
            return {
                "demand": normalize_demand_payload(query, city_name, payload, "llm"),
                "source": "llm",
                "llmUsed": True,
                "degraded": False,
                "message": "cloud llm demand parsing succeeded",
            }
        except RuntimeError as error:
            return {
                "demand": fallback,
                "source": "rule",
                "llmUsed": False,
                "degraded": True,
                "message": str(error),
            }
