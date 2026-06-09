"""Lambda handler for KR raw JSON transform."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, cast

from kr_details_pipeline import transform
from kr_details_pipeline.transform import TransformResult


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    import boto3

    bucket = str(event["bucket"])
    raw_prefix = str(event.get("source_prefix", "raw/KR/details"))
    ingest_date = str(event.get("ingest_date") or datetime.utcnow().strftime("%Y%m%d"))
    processed_prefix = str(event.get("processed_prefix", "processed/KR"))
    source_key_prefix = f"{raw_prefix.rstrip('/')}/{ingest_date}/"
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    manifest_key = f"{processed_prefix.rstrip('/')}/manifest/{run_id}/summary.json"

    s3 = boto3.client("s3")
    processed_keys: list[str] = []
    failed_keys: list[str] = []
    passed_city = 0
    review_city = 0
    failed_city = 0

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=source_key_prefix):
        for item in page.get("Contents", []):
            key = str(item.get("Key", ""))
            if not key.endswith(".json"):
                continue

            record = _handle_raw_item(s3=s3, bucket=bucket, key=key, processed_prefix=processed_prefix.rstrip("/"))
            processed_keys.append(key)
            if record["status"] == "ok":
                if record["city_summary"] == "passed":
                    passed_city += 1
                elif record["city_summary"] == "review":
                    review_city += 1
                else:
                    failed_city += 1
            else:
                failed_city += 1
                failed_keys.append(key)

    summary = {
        "status": "ok" if failed_city == 0 else "partial",
        "ingest_date": ingest_date,
        "run_id": run_id,
        "source_prefix": source_key_prefix,
        "city_processed": len(processed_keys),
        "processed_count": passed_city + review_city + failed_city,
        "review_count": review_city,
        "failed_count": failed_city,
        "total_found": len(processed_keys),
        "city_failed": failed_keys,
    }

    s3.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=transform.as_json(summary),
        ContentType="application/json",
        Metadata={
            "pipeline_stage": "kr-transformer",
            "ingest_date": ingest_date,
            "run_id": run_id,
        },
    )

    return {"statusCode": 200 if summary["status"] == "ok" else 207, "summary_key": manifest_key, "summary": summary}


def _handle_raw_item(*, s3: Any, bucket: str, key: str, processed_prefix: str) -> dict[str, Any]:
    try:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
        payload = json.loads(body)
    except Exception as exc:
        return {"status": "failed", "source_key": key, "city_name_en": "", "city_id": "", "reason": str(exc)}

    try:
        city_result = transform.transform_raw_city(cast(dict[str, Any], payload), source_key=key)
    except Exception as exc:
        return {"status": "failed", "source_key": key, "city_name_en": "", "city_id": "", "reason": str(exc)}

    _write_city_outputs(s3=s3, bucket=bucket, raw_key=key, processed_prefix=processed_prefix, result=city_result, raw_payload=cast(dict[str, Any], payload))

    city_summary = _summarize_city_result(city_result)
    return {
        "status": "ok",
        "source_key": key,
        "city_name_en": city_result.city_name_en,
        "city_id": city_result.city_id,
        "city_summary": city_summary,
        "passed_count": len(city_result.passed),
        "review_count": len(city_result.review),
        "failed_count": len(city_result.failed),
    }


def _write_city_outputs(
    *,
    s3: Any,
    bucket: str,
    raw_key: str,
    processed_prefix: str,
    result: TransformResult,
    raw_payload: dict[str, Any],
) -> None:
    ingest_date = raw_key.split("/")[-2]
    destination_prefix = f"{processed_prefix}/details/{ingest_date}"
    base_record = {
        "city_id": result.city_id,
        "city_name_en": result.city_name_en,
        "city_record": transform.build_city_record(raw_payload),
    }

    if result.passed:
        s3.put_object(
            Bucket=bucket,
            Key=f"{destination_prefix}/passed/{raw_key.split('/')[-1]}",
            Body=transform.as_json({"status": "passed", **base_record, "records": result.passed}),
            ContentType="application/json",
        )
    if result.review:
        s3.put_object(
            Bucket=bucket,
            Key=f"{destination_prefix}/review/{raw_key.split('/')[-1]}",
            Body=transform.as_json({"status": "review", **base_record, "records": result.review}),
            ContentType="application/json",
        )
    if result.failed:
        s3.put_object(
            Bucket=bucket,
            Key=f"{destination_prefix}/failed/{raw_key.split('/')[-1]}",
            Body=transform.as_json({"status": "failed", **base_record, "records": result.failed}),
            ContentType="application/json",
        )


def _summarize_city_result(result: TransformResult) -> str:
    if result.failed:
        return "failed"
    if result.review:
        return "review"
    return "passed"
