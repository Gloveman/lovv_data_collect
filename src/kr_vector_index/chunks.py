"""Build rich embedding text chunks for S3 Vector indexing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from kr_vector_index.metadata import compact_metadata, validate_metadata

EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"


@dataclass(frozen=True)
class VectorChunk:
    key: str
    place_id: str
    embedding_text: str
    metadata: dict[str, Any]


def build_chunk(item: dict[str, Any], *, chunk_no: int = 0) -> VectorChunk:
    entity_type = _normalize_entity_type(str(item.get("entity_type") or "unknown"))
    source_id = str(item.get("content_id") or item.get("entity_id") or _sk_source_id(item) or "unknown")
    place_id = f"{entity_type}#{source_id}"
    key = f"{place_id}#{chunk_no}"
    text = build_embedding_text(item, entity_type=entity_type)
    metadata = validate_metadata(
        compact_metadata(
            {
                "country": "KR",
                "province": item.get("province"),
                "city_id": item.get("city_id"),
                "city_name_en": item.get("city_name_en"),
                "city_name_ko": item.get("city_name_ko"),
                "entity_type": entity_type,
                "source_type": entity_type,
                "source_id": source_id,
                "place_id": place_id,
                "title": item.get("title"),
                "theme_tags": _tags(item, entity_type),
                "season_tags": item.get("season_tags"),
                "visit_months": item.get("visit_months"),
                "latitude": _number(item.get("latitude")),
                "longitude": _number(item.get("longitude")),
                "raw_s3_uri": item.get("source") or item.get("raw_s3_uri") or "unknown",
                "ddb_pk": item.get("PK"),
                "ddb_sk": item.get("SK"),
                "embedding_model": EMBEDDING_MODEL,
            }
        )
    )
    return VectorChunk(key=key, place_id=place_id, embedding_text=text, metadata=metadata)


def build_chunks(items: list[dict[str, Any]]) -> list[VectorChunk]:
    return [build_chunk(item) for item in items]


def build_embedding_text(item: dict[str, Any], *, entity_type: str) -> str:
    title = str(item.get("title") or item.get("city_name_ko") or item.get("city_name_en") or "")
    lines = [
        f"이름: {title}",
        f"유형: {_type_label(entity_type)}",
        f"도시: {item.get('city_name_ko') or ''} ({item.get('city_name_en') or ''})",
        f"지역: {item.get('province') or ''}",
    ]
    address = str(item.get("address") or item.get("venue") or "")
    if address:
        lines.append(f"주소: {address}")

    if entity_type == "restaurant":
        _append(lines, "음식 카테고리", item.get("restaurant_category"))
        _append(lines, "대표메뉴", item.get("signature_menu"))
        _append(lines, "운영시간", item.get("opening_hours"))
        _append(lines, "휴무", item.get("closed_days"))
    elif entity_type == "festival":
        _append(lines, "기간", _date_range(item))
        _append(lines, "장소", item.get("venue"))
        _append(lines, "계절", item.get("season"))
    elif entity_type == "attraction":
        _append(lines, "테마", item.get("theme"))
    else:
        _append(lines, "도시 ID", item.get("city_id"))

    _append(lines, "설명", item.get("description"))
    return "\n".join(line for line in lines if line.strip())


def _normalize_entity_type(entity_type: str) -> str:
    return "city" if entity_type == "city_metadata" else entity_type


def _type_label(entity_type: str) -> str:
    return {
        "city": "도시",
        "attraction": "관광지",
        "restaurant": "음식점",
        "festival": "축제",
    }.get(entity_type, entity_type)


def _append(lines: list[str], label: str, value: Any) -> None:
    if value not in (None, "", [], {}):
        lines.append(f"{label}: {value}")


def _date_range(item: dict[str, Any]) -> str:
    start = item.get("eventstartdate") or item.get("event_start_date") or ""
    end = item.get("eventenddate") or item.get("event_end_date") or ""
    return f"{start}~{end}".strip("~")


def _tags(item: dict[str, Any], entity_type: str) -> list[str]:
    raw = item.get("theme_tags") or item.get("season_tags") or []
    if isinstance(raw, list):
        tags = [str(value) for value in raw if value]
    else:
        tags = [str(raw)] if raw else []
    category = item.get("restaurant_category") if entity_type == "restaurant" else item.get("theme")
    if category:
        tags.append(str(category))
    return list(dict.fromkeys(tags))


def _number(value: Any) -> float | int | None:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (float, int)):
        return value
    return None


def _sk_source_id(item: dict[str, Any]) -> str:
    sk = str(item.get("SK") or "")
    return sk.split("#", 1)[1] if "#" in sk else sk
