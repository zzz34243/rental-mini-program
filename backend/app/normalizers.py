from __future__ import annotations

from .collectors import RawListing
from .models import House, now_text


def build_embedding_text(payload: dict) -> str:
    parts = [
        str(payload.get("cityName", "")).strip(),
        str(payload.get("districtText", "")).strip(),
        str(payload.get("communityName", "")).strip(),
        str(payload.get("title", "")).strip(),
        str(payload.get("meta", "")).strip(),
        str(payload.get("priceText", "")).strip(),
        " ".join(str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()),
        str(payload.get("summary", "")).strip(),
        str(payload.get("trafficText", "")).strip(),
        str(payload.get("lifestyleText", "")).strip(),
        str(payload.get("searchText", "")).strip(),
    ]
    return " ".join(part for part in parts if part).strip()


def normalize_listing(raw_listing: RawListing) -> House:
    payload = raw_listing.payload
    updated_at = now_text()

    return House(
        id=str(payload.get("id") or f"{raw_listing.source_name}-{raw_listing.external_id}"),
        sourceName=raw_listing.source_name,
        sourceListingId=str(payload.get("sourceListingId") or raw_listing.external_id),
        sourceUrl=str(payload.get("sourceUrl") or ""),
        category=str(payload.get("category") or "rent"),
        intentLabel=str(payload.get("intentLabel") or ("买房" if payload.get("category") == "buy" else "租房")),
        cityName=str(payload.get("cityName") or "北京"),
        title=str(payload.get("title") or ""),
        communityName=str(payload.get("communityName") or ""),
        priceText=str(payload.get("priceText") or ""),
        meta=str(payload.get("meta") or ""),
        districtText=str(payload.get("districtText") or ""),
        tags=[str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()],
        summary=str(payload.get("summary") or ""),
        scoreText=str(payload.get("scoreText") or ""),
        highlightTitle=str(payload.get("highlightTitle") or "推荐理由"),
        highlightText=str(payload.get("highlightText") or ""),
        trafficText=str(payload.get("trafficText") or ""),
        lifestyleText=str(payload.get("lifestyleText") or ""),
        searchText=str(payload.get("searchText") or ""),
        embeddingText=str(payload.get("embeddingText") or build_embedding_text(payload)),
        embeddingModel=str(payload.get("embeddingModel") or ""),
        embeddingVector=[
            float(item)
            for item in payload.get("embeddingVector", [])
            if isinstance(item, (int, float))
        ],
        isActive=bool(payload.get("isActive", True)),
        createdAt=str(payload.get("createdAt") or updated_at),
        updatedAt=updated_at,
    )
