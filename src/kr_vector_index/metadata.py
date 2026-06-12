"""S3 Vector metadata allowlist and size checks."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

FILTERABLE_METADATA_KEYS = {
    "country",
    "province",
    "city_id",
    "city_name_en",
    "city_name_ko",
    "entity_type",
    "source_type",
    "source_id",
    "place_id",
    "title",
    "theme_tags",
    "season_tags",
    "visit_months",
    "latitude",
    "longitude",
}
NON_FILTERABLE_METADATA_KEYS = {"raw_s3_uri", "ddb_pk", "ddb_sk", "embedding_model"}
ALLOWED_METADATA_KEYS = FILTERABLE_METADATA_KEYS | NON_FILTERABLE_METADATA_KEYS
FILTERABLE_METADATA_BUDGET_BYTES = 2048


class MetadataValidationError(ValueError):
    """Raised when S3 Vector metadata violates the project contract."""


def validate_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    metadata = {key: _json_safe(value) for key, value in metadata.items()}
    unknown_keys = set(metadata) - ALLOWED_METADATA_KEYS
    if unknown_keys:
        raise MetadataValidationError(f"metadata keys are not allowlisted: {sorted(unknown_keys)}")

    filterable = {key: value for key, value in metadata.items() if key in FILTERABLE_METADATA_KEYS}
    encoded = json.dumps(filterable, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > FILTERABLE_METADATA_BUDGET_BYTES:
        raise MetadataValidationError(
            f"filterable metadata is {len(encoded)} bytes, exceeds {FILTERABLE_METADATA_BUDGET_BYTES}"
        )
    return metadata


def compact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: _json_safe(value) for key, value in metadata.items() if value not in (None, "", [], {})}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value
