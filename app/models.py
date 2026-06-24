from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@dataclass(slots=True)
class House:
    id: str
    sourceName: str
    sourceListingId: str
    sourceUrl: str
    category: str
    intentLabel: str
    cityName: str
    title: str
    communityName: str
    priceText: str
    meta: str
    districtText: str
    tags: list[str]
    summary: str
    scoreText: str
    highlightTitle: str
    highlightText: str
    trafficText: str
    lifestyleText: str
    searchText: str
    embeddingText: str = ""
    embeddingModel: str = ""
    embeddingVector: list[float] = field(default_factory=list)
    isActive: bool = True
    createdAt: str = field(default_factory=now_text)
    updatedAt: str = field(default_factory=now_text)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Review:
    id: str
    houseTitle: str
    communityName: str
    score: int
    livingTags: list[str]
    content: str
    displayName: str
    createdAt: str = field(default_factory=now_text)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AIHistoryRecord:
    id: str
    userText: str
    summary: str
    demandTags: list[str]
    intentLabel: str
    recommendIds: list[str]
    createdAt: str = field(default_factory=now_text)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FavoriteRecord:
    houseId: str
    createdAt: str = field(default_factory=now_text)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CollectionRun:
    id: str
    sources: list[str]
    cityName: str
    category: str
    status: str
    collectedCount: int
    message: str
    createdAt: str = field(default_factory=now_text)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
