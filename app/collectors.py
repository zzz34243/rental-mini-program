from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from html import unescape
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .sample_data import DEFAULT_HOUSES


@dataclass(slots=True)
class RawListing:
    source_name: str
    external_id: str
    payload: dict[str, Any]


class CollectorError(RuntimeError):
    """Raised when a remote source cannot be fetched or parsed."""


class DemoPublicListingCollector:
    name = "demo-public-feed"

    def collect(self, *, city_name: str = "", category: str = "") -> list[RawListing]:
        listings = self._collect_with_filters(city_name=city_name, category=category)
        if listings or not city_name:
            return listings
        return self._collect_with_filters(city_name="", category=category)

    def _collect_with_filters(self, *, city_name: str = "", category: str = "") -> list[RawListing]:
        items = []
        for house in DEFAULT_HOUSES:
            if city_name and house.cityName != city_name:
                continue
            if category and category != "all" and house.category != category:
                continue
            items.append(
                RawListing(
                    source_name=self.name,
                    external_id=house.sourceListingId,
                    payload=asdict(house),
                )
            )
        return items


class LianjiaHomepageCollector:
    name = "lianjia-home-recommend"
    city_slug_map = {
        "北京": "bj",
    }
    section_pattern = re.compile(
        r'<ul class="lists mod_ershoufang active">(.*?)</ul>',
        re.IGNORECASE | re.DOTALL,
    )
    item_pattern = re.compile(r'<li class="pictext">(.*?)</li>', re.IGNORECASE | re.DOTALL)
    href_pattern = re.compile(r'<a href="([^"]+?/(\d+)\.html)"', re.IGNORECASE)
    title_pattern = re.compile(r'<div class="item_main">(.*?)</div>', re.IGNORECASE | re.DOTALL)
    other_pattern = re.compile(
        r'<div class="item_other[^"]*" title="([^"]*)">([^<]*)</div>',
        re.IGNORECASE | re.DOTALL,
    )
    price_pattern = re.compile(
        r'<span class="price_total"><em>([^<]+)</em><span class="unit">([^<]+)</span></span><span class="unit_price">([^<]*)</span>',
        re.IGNORECASE | re.DOTALL,
    )
    tag_pattern = re.compile(r'<span class="tag"[^>]*>([^<]+)</span>', re.IGNORECASE)
    desc_pattern = re.compile(r'<div class="item_desc">([^<]+)</div>', re.IGNORECASE | re.DOTALL)
    tag_strip_pattern = re.compile(r"<[^>]+>")
    whitespace_pattern = re.compile(r"\s+")

    def collect(self, *, city_name: str = "", category: str = "") -> list[RawListing]:
        if category and category not in ("all", "buy"):
            return []

        city_slug = self.city_slug_map.get(city_name or "北京")
        if not city_slug:
            return []

        html = self._fetch_html(f"https://m.lianjia.com/{city_slug}/")
        return self._parse_homepage(html=html, city_name=city_name or "北京")

    def _fetch_html(self, url: str) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        )
        try:
            with urlopen(request, timeout=15) as response:
                return response.read().decode("utf-8", errors="ignore")
        except URLError as error:
            raise CollectorError(f"{self.name} fetch failed: {error}") from error

    def _parse_homepage(self, *, html: str, city_name: str) -> list[RawListing]:
        section_match = self.section_pattern.search(html)
        if not section_match:
            raise CollectorError(f"{self.name} parse failed: ershoufang section not found")

        items = []
        for block in self.item_pattern.findall(section_match.group(1)):
            href_match = self.href_pattern.search(block)
            title_match = self.title_pattern.search(block)
            other_match = self.other_pattern.search(block)
            price_match = self.price_pattern.search(block)

            if not (href_match and title_match and other_match and price_match):
                continue

            source_url, external_id = href_match.groups()
            title = self._clean_text(title_match.group(1))
            area_title = self._clean_text(other_match.group(1)).replace("二手房", "")
            meta_text = self._clean_text(other_match.group(2))
            district = self._extract_last_segment(meta_text)
            total_price, price_unit, unit_price = [self._clean_text(part) for part in price_match.groups()]
            tags = [self._clean_text(tag) for tag in self.tag_pattern.findall(block)]
            desc_match = self.desc_pattern.search(block)
            desc_text = self._clean_text(desc_match.group(1)) if desc_match else ""

            payload = {
                "id": f"lianjia-buy-{external_id}",
                "sourceListingId": external_id,
                "sourceUrl": source_url,
                "category": "buy",
                "intentLabel": "买房",
                "cityName": city_name,
                "title": title,
                "communityName": area_title or district or city_name,
                "priceText": f"{total_price}{price_unit}",
                "meta": meta_text,
                "districtText": district or area_title or city_name,
                "tags": [tag for tag in tags if tag],
                "summary": desc_text or f"来自链家移动站推荐流，板块为{district or area_title or city_name}。",
                "scoreText": unit_price,
                "highlightTitle": "采集来源",
                "highlightText": "来自链家移动站首页推荐流。",
                "trafficText": self._build_traffic_text(tags, meta_text),
                "lifestyleText": self._build_lifestyle_text(tags, area_title or district or city_name),
                "searchText": " ".join(
                    [
                        city_name,
                        title,
                        area_title,
                        district,
                        meta_text,
                        unit_price,
                        " ".join(tags),
                        desc_text,
                    ]
                ).strip(),
            }
            items.append(
                RawListing(
                    source_name=self.name,
                    external_id=external_id,
                    payload=payload,
                )
            )

        if not items:
            raise CollectorError(f"{self.name} parse failed: no listing cards found")

        return items

    def _clean_text(self, text: str) -> str:
        return self.whitespace_pattern.sub(" ", unescape(self.tag_strip_pattern.sub(" ", text or ""))).strip()

    @staticmethod
    def _extract_last_segment(meta_text: str) -> str:
        parts = [part.strip() for part in meta_text.split("/") if part.strip()]
        return parts[-1] if parts else ""

    @staticmethod
    def _build_traffic_text(tags: list[str], meta_text: str) -> str:
        if any("地铁" in tag for tag in tags):
            return f"标签显示近轨道交通，基础户型信息为：{meta_text}"
        return f"基础户型信息为：{meta_text}"

    @staticmethod
    def _build_lifestyle_text(tags: list[str], area_text: str) -> str:
        if tags:
            return f"当前抓取到的标签包括：{'、'.join(tags)}，所属板块：{area_text}"
        return f"当前来源仅抓取到基础房源信息，所属板块：{area_text}"


class CollectorRegistry:
    def __init__(self) -> None:
        self.collectors = [
            DemoPublicListingCollector(),
            LianjiaHomepageCollector(),
        ]

    def list_sources(self) -> list[str]:
        return [collector.name for collector in self.collectors]

    def collect(
        self,
        *,
        city_name: str = "",
        category: str = "",
        source_names: list[str] | None = None,
    ) -> tuple[list[RawListing], list[str]]:
        items: list[RawListing] = []
        errors: list[str] = []
        allowed = set(source_names or [])
        for collector in self.collectors:
            if allowed and collector.name not in allowed:
                continue
            try:
                items.extend(collector.collect(city_name=city_name, category=category))
            except CollectorError as error:
                errors.append(str(error))
        return items, errors
