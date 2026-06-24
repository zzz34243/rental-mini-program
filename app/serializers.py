from __future__ import annotations

from typing import Any


HOUSE_INTERNAL_FIELDS = {
    "embeddingModel",
    "embeddingText",
    "embeddingVector",
}


def serialize_house(
    house: dict[str, Any],
    *,
    include_internal: bool = False,
) -> dict[str, Any]:
    payload = dict(house)
    if include_internal:
        return payload

    for field in HOUSE_INTERNAL_FIELDS:
        payload.pop(field, None)
    return payload


def serialize_house_list(
    houses: list[dict[str, Any]],
    *,
    include_internal: bool = False,
) -> list[dict[str, Any]]:
    return [
        serialize_house(item, include_internal=include_internal)
        for item in houses
    ]
