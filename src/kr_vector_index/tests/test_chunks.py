from kr_vector_index.chunks import build_chunk


def test_restaurant_chunk_includes_dynamodb_address() -> None:
    item = {
        "PK": "CITY#Andong",
        "SK": "RESTAURANT#100",
        "entity_type": "restaurant",
        "content_id": "100",
        "entity_id": "REST-100",
        "city_id": "KR-Andong",
        "city_name_en": "Andong",
        "city_name_ko": "안동",
        "province": "경상북도",
        "title": "안동식당",
        "address": "경상북도 안동시 풍천면 풍요6길 17-2",
        "description": "지역 식당 설명",
        "restaurant_category": "한식",
        "signature_menu": "간고등어",
        "opening_hours": "10:00~20:00",
        "closed_days": "월요일",
        "longitude": 128.1,
        "latitude": 36.5,
        "quality_status": "passed",
    }

    chunk = build_chunk(item)

    assert chunk.key == "restaurant#100#0"
    assert chunk.place_id == "restaurant#100"
    assert "주소: 경상북도 안동시 풍천면 풍요6길 17-2" in chunk.embedding_text
    assert "대표메뉴: 간고등어" in chunk.embedding_text
    assert chunk.metadata["ddb_pk"] == "CITY#Andong"
    assert chunk.metadata["ddb_sk"] == "RESTAURANT#100"


def test_build_chunk_is_deterministic_for_same_item() -> None:
    item = {
        "PK": "CITY#Andong",
        "SK": "ATTRACTION#200",
        "entity_type": "attraction",
        "content_id": "200",
        "entity_id": "ATTR-200",
        "city_id": "KR-Andong",
        "city_name_en": "Andong",
        "title": "하회마을",
        "address": "경상북도 안동시 풍천면",
        "description": "관광지 설명",
        "theme": "history",
    }

    assert build_chunk(item) == build_chunk(item)
