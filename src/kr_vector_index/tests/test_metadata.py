import pytest
from decimal import Decimal

from kr_vector_index.metadata import MetadataValidationError, validate_metadata


def test_validate_metadata_accepts_allowlisted_keys() -> None:
    metadata = {
        "country": "KR",
        "entity_type": "restaurant",
        "city_id": "KR-Andong",
        "theme_tags": ["한식"],
        "raw_s3_uri": "s3://bucket/key.json",
        "ddb_pk": "CITY#Andong",
        "ddb_sk": "RESTAURANT#100",
        "embedding_model": "amazon.titan-embed-text-v2:0",
    }

    assert validate_metadata(metadata) == metadata


def test_validate_metadata_rejects_unknown_key() -> None:
    with pytest.raises(MetadataValidationError, match="not allowlisted"):
        validate_metadata({"country": "KR", "unknown": "value"})


def test_validate_metadata_rejects_large_filterable_metadata() -> None:
    with pytest.raises(MetadataValidationError, match="filterable metadata"):
        validate_metadata({"country": "KR", "title": "x" * 3000})


def test_validate_metadata_normalizes_decimal_values() -> None:
    metadata = validate_metadata({"latitude": Decimal("36.5"), "longitude": Decimal("128.1")})

    assert metadata == {"latitude": 36.5, "longitude": 128.1}
