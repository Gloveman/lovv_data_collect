"""Manifest and quality summary helpers for S3 Vector builds."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def build_manifest(
    *,
    index_name: str,
    entity_counts: dict[str, int],
    chunk_count: int,
    vector_success_count: int,
    failed_count: int = 0,
) -> dict[str, Any]:
    return {
        "index_name": index_name,
        "index_text_mode": "rich",
        "created_at": datetime.now(UTC).isoformat(),
        "entity_counts": entity_counts,
        "chunk_count": chunk_count,
        "vector_success_count": vector_success_count,
        "failed_count": failed_count,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
