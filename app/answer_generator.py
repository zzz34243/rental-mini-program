from __future__ import annotations

from typing import Any

from .llm_client import LLMClient


def _build_house_brief(house: dict[str, Any], index: int) -> str:
    tags = "、".join(str(tag).strip() for tag in house.get("tags", []) if str(tag).strip())
    return (
        f"{index}. {house.get('title', '')}\n"
        f"价格：{house.get('priceText', '')}\n"
        f"区域：{house.get('districtText', '')}\n"
        f"亮点：{tags or house.get('summary', '')}\n"
        f"摘要：{house.get('summary', '')}\n"
    )


def build_template_answer(summary: str, demand: dict[str, Any], recommend_list: list[dict[str, Any]]) -> str:
    if not recommend_list:
        return "当前没有找到足够匹配的房源，可以放宽预算、区域或标签条件后重试。"

    top_titles = "、".join(item.get("title", "") for item in recommend_list[:3] if item.get("title"))
    demand_tags = demand.get("demandTags", [])
    tag_text = "、".join(demand_tags[:3]) if demand_tags else "综合条件"
    if top_titles:
        return f"{summary} 当前优先返回与{tag_text}更接近的房源，建议重点比较：{top_titles}。"
    return f"{summary} 当前结果按本地匹配分排序，建议先查看前几套房源的价格、标签和通勤信息。"


class AnswerGenerator:
    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    def generate(
        self,
        *,
        query: str,
        summary: str,
        demand: dict[str, Any],
        recommend_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        fallback_text = build_template_answer(summary, demand, recommend_list)
        if not recommend_list:
            return {
                "text": fallback_text,
                "source": "template",
                "llmUsed": False,
                "degraded": False,
                "message": "no recommend list available",
            }

        if not self.llm_client.is_configured():
            return {
                "text": fallback_text,
                "source": "template",
                "llmUsed": False,
                "degraded": False,
                "message": "cloud llm is not configured",
            }

        system_prompt = (
            "你是房产推荐说明助手。"
            "你只能基于给定房源生成简短说明，不允许虚构房源信息，不允许改变给定顺序。"
            "输出 2 到 4 句中文，先总结需求，再说明前两三套为什么匹配。"
        )
        house_briefs = "\n".join(
            _build_house_brief(house, index + 1)
            for index, house in enumerate(recommend_list[:5])
        )
        user_prompt = (
            f"用户需求：{query}\n"
            f"结构化需求：{demand}\n"
            f"检索摘要：{summary}\n"
            f"候选房源：\n{house_briefs}\n"
            "请输出推荐说明。"
        )

        try:
            text = self.llm_client.complete_text(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.3,
            )
            return {
                "text": text.strip() or fallback_text,
                "source": "llm",
                "llmUsed": True,
                "degraded": False,
                "message": "cloud llm answer generation succeeded",
            }
        except RuntimeError as error:
            return {
                "text": fallback_text,
                "source": "template",
                "llmUsed": False,
                "degraded": True,
                "message": str(error),
            }
