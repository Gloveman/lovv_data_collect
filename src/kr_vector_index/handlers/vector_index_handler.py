"""Lambda handler for KR S3 Vector index build operations."""

from __future__ import annotations

import json
import os
from typing import Any

from kr_vector_index.chunks import build_chunks
from kr_vector_index.embed import embed_chunks
from kr_vector_index.export import count_by_entity_type, export_items
from kr_vector_index.manifest import build_manifest
from kr_vector_index.upsert import build_vector_records, put_vectors_sdk


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    command = str(event.get("command") or "export-counts")
    if command not in {"export-counts", "build"}:
        return {"statusCode": 400, "error": f"unsupported command: {command}"}

    dry_run = bool(event.get("dry_run", False))

    import boto3

    table_name = str(event.get("table_name") or os.environ.get("DYNAMODB_TABLE") or "TourKoreaDomainData")
    vector_bucket = str(event.get("vector_bucket") or os.environ.get("VECTOR_BUCKET") or "lovv-vector-dev")
    index_name = str(event.get("index_name") or os.environ.get("VECTOR_INDEX") or "kr-tour-domain-v1")
    manifest_bucket = str(event.get("manifest_bucket") or os.environ.get("MANIFEST_BUCKET") or "")
    manifest_prefix = str(event.get("manifest_prefix") or os.environ.get("MANIFEST_PREFIX") or "processed/KR/vector/manifests")
    city_pk = event.get("city_pk")
    max_items = _positive_int(event.get("max_items"))
    ddb = boto3.client("dynamodb")
    items = export_items(ddb, table_name=table_name, city_pk=str(city_pk) if city_pk else None)
    if max_items:
        items = items[:max_items]
    entity_counts = count_by_entity_type(items)

    if command == "export-counts":
        return {
            "statusCode": 200,
            "summary": {
                "command": command,
                "table_name": table_name,
                "city_pk": city_pk,
                "entity_counts": entity_counts,
                "item_count": len(items),
            },
        }

    chunks = build_chunks(items)
    vector_success_count = 0
    if not dry_run:
        bedrock = boto3.client("bedrock-runtime")
        s3vectors = boto3.client("s3vectors")
        embeddings = embed_chunks(bedrock, chunks)
        records = build_vector_records(chunks, embeddings)
        vector_success_count = put_vectors_sdk(
            s3vectors,
            records,
            vector_bucket=vector_bucket,
            index_name=index_name,
        )

    manifest = build_manifest(
        index_name=index_name,
        entity_counts=entity_counts,
        chunk_count=len(chunks),
        vector_success_count=vector_success_count,
    )
    manifest_s3_uri = None
    if manifest_bucket:
        manifest_s3_uri = _put_manifest(
            boto3.client("s3"),
            bucket=manifest_bucket,
            prefix=manifest_prefix,
            manifest=manifest,
        )

    return {
        "statusCode": 200,
        "summary": {
            "command": command,
            "dry_run": dry_run,
            "table_name": table_name,
            "vector_bucket": vector_bucket,
            "index_name": index_name,
            "city_pk": city_pk,
            "max_items": max_items,
            "entity_counts": entity_counts,
            "item_count": len(items),
            "chunk_count": len(chunks),
            "vector_success_count": vector_success_count,
            "manifest_s3_uri": manifest_s3_uri,
        },
        "manifest": manifest,
    }


def _positive_int(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    parsed = int(value)
    if parsed < 1:
        raise ValueError("max_items must be >= 1")
    return parsed


def _put_manifest(client: Any, *, bucket: str, prefix: str, manifest: dict[str, Any]) -> str:
    key = f"{prefix.strip('/')}/latest.json"
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )
    return f"s3://{bucket}/{key}"
