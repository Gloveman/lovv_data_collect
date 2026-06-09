"""Transformation rules for KR raw city detail payloads."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any


DATE_FORMATS = ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d")
KR_BOUNDS = {
    "lon_min": 124.0,
    "lon_max": 132.0,
    "lat_min": 33.0,
    "lat_max": 39.0,
}


@dataclass(frozen=True)
class TransformResult:
    city_id: str
    city_name_en: str
    passed: list[dict[str, Any]]
    review: list[dict[str, Any]]
    failed: list[dict[str, Any]]


def build_city_record(payload: dict[str, Any]) -> dict[str, Any]:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    city_name_en = str(meta.get("city_name_en") or "UNKNOWN")
    return {
        "city_id": _build_city_id(meta, city_name_en),
        "city_name_en": city_name_en,
        "city_name_ko": str(meta.get("city_name_ko") or ""),
        "province": str(meta.get("province") or ""),
        "lDongRegnCd": str(meta.get("lDongRegnCd") or ""),
        "lDongSignguCd": str(meta.get("lDongSignguCd") or ""),
        "attraction_count": len(payload.get("attractions") or [])
        if isinstance(payload.get("attractions"), list)
        else 0,
        "festival_count": len(payload.get("festivals") or [])
        if isinstance(payload.get("festivals"), list)
        else 0,
        "visitor_statistics_count": len(payload.get("visitor_statistics") or [])
        if isinstance(payload.get("visitor_statistics"), list)
        else 0,
    }


def transform_raw_city(payload: dict[str, Any], source_key: str | None = None) -> TransformResult:
    city_name_en = str((payload.get("meta") or {}).get("city_name_en") or "UNKNOWN")
    city_id = _build_city_id((payload.get("meta") or {}), city_name_en)
    passed: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    city_record = build_city_record(payload)

    for record in _iter_content_items(payload):
        transformed = transform_content_record(record, city_record, source_key=source_key)
        status = str(transformed.get("quality_status") or "failed")
        if status == "passed":
            passed.append(transformed)
        elif status == "review":
            review.append(transformed)
        else:
            failed.append(transformed)

    for record in _iter_visitor_statistics(payload):
        transformed = transform_visitor_statistic(record, city_record)
        status = str(transformed.get("quality_status") or "failed")
        if status == "passed":
            passed.append(transformed)
        elif status == "review":
            review.append(transformed)
        else:
            failed.append(transformed)

    if not payload.get("meta"):
        failed.append(
            {
                "entity_type": "city",
                "entity_id": city_id,
                "quality_status": "failed",
                "review_queues": ["source_review"],
                "message": "Missing meta block",
                "source_key": source_key or "",
            }
        )

    return TransformResult(
        city_id=city_id,
        city_name_en=city_name_en,
        passed=passed,
        review=review,
        failed=failed,
    )


def transform_content_record(record: dict[str, Any], city_record: dict[str, Any], *, source_key: str | None = None) -> dict[str, Any]:
    content_id = str(record.get("contentid") or "").strip()
    title = str(record.get("title") or "").strip()
    content_type_id = str(record.get("contenttypeid") or "")
    if content_type_id == "15":
        entity_type = "festival"
        entity_id = f"FEST-{content_id}"
        sk_prefix = "FESTIVAL"
    else:
        entity_type = "attraction"
        entity_id = f"ATT-{content_id}"
        sk_prefix = "ATTRACTION"

    geo_ok, lon, lat, geo_issues = _validate_coordinates(record.get("mapx"), record.get("mapy"))
    detail = record.get("detail")
    if not isinstance(detail, dict):
        detail = {}
    common = detail.get("common") if isinstance(detail.get("common"), dict) else {}
    intro = detail.get("intro") if isinstance(detail.get("intro"), dict) else {}
    detail_description = _first_non_empty(
        str(common.get("overview") or ""),
        str(intro.get("overview") or ""),
        str(detail.get("overview") or ""),
    )

    issues: list[str] = []
    if not content_id:
        issues.append("missing_contentid")
    if not title:
        issues.append("missing_title")
    if not geo_ok:
        issues.append("location_review")
    assigned_theme = _first_non_empty(str(record.get("_assigned_theme") or ""), str(intro.get("cat3") or ""), str(record.get("cat3") or ""))
    if not assigned_theme:
        issues.append("theme_review")
    if "tel" not in record and "tel" not in common and "infocenter" not in record and not _first_non_empty(
        str(record.get("tel") or ""),
        str(common.get("tel") or ""),
        str(intro.get("infocenter") or ""),
    ):
        issues.append("contact_review")

    quality_status = _calc_quality_status(issues)
    event_start = _to_iso_date(str(intro.get("eventstartdate") or record.get("eventstartdate") or ""))
    event_end = _to_iso_date(str(intro.get("eventenddate") or record.get("eventenddate") or ""))
    season_tags = []
    if event_start:
        season_tags.append(_month_to_season(int(event_start[5:7])))
    visit_months = []
    if event_start and event_end:
        visit_months = _derive_visit_months(event_start, event_end)

    return {
        "entity_type": entity_type,
        "source_key": source_key or "",
        "city_id": city_record["city_id"],
        "city_name_en": city_record["city_name_en"],
        "PK": f"CITY#{city_record['city_name_en']}",
        "SK": f"{sk_prefix}#{content_id}",
        "entity_id": entity_id,
        "content_id": content_id,
        "contenttypeid": content_type_id or None,
        "title": title,
        "description": detail_description,
        "theme": assigned_theme,
        "theme_tags": [assigned_theme] if assigned_theme else [],
        "phone": _first_non_empty(
            str(record.get("tel") or ""),
            str(common.get("tel") or ""),
            str(intro.get("infocenter") or ""),
        ),
        "image_url": _first_non_empty(
            str(record.get("firstimage") or ""),
            str(common.get("firstimage") or ""),
            str(record.get("firstimage2") or ""),
        ),
        "address": _first_non_empty(str(record.get("addr1") or ""), str(intro.get("addr1") or "")),
        "longitude": lon,
        "latitude": lat,
        "geohash": None,
        "geohash_prefix": None,
        "eventstartdate": event_start,
        "eventenddate": event_end,
        "month": int(event_start[5:7]) if event_start else None,
        "season": _month_to_season(int(event_start[5:7])) if event_start else None,
        "season_tags": season_tags,
        "visit_months": visit_months,
        "quality_status": quality_status,
        "review_queues": list(dict.fromkeys(issues)),
    }


def transform_visitor_statistic(monthly: dict[str, Any], city_record: dict[str, Any]) -> dict[str, Any]:
    month = str(monthly.get("month") or "").strip()
    if month:
        if re.fullmatch(r"\d{4}-\d{2}", month):
            month = month.replace("-", "")
        elif not re.fullmatch(r"\d{6}", month):
            try:
                month_dt = datetime.strptime(month, "%Y%m")
                month = month_dt.strftime("%Y%m")
            except Exception:
                month = ""

    quality_status = "passed" if month else "failed"
    review_queues = ["source_review"] if not month else []

    return {
        "entity_type": "visitor_statistics",
        "city_id": city_record["city_id"],
        "city_name_en": city_record["city_name_en"],
        "PK": f"CITY#{city_record['city_name_en']}",
        "SK": f"STAT#{month}" if month else "STAT#UNKNOWN",
        "entity_id": f"KR-STAT-{city_record['city_id']}-{month}" if month else f"KR-STAT-{city_record['city_id']}-UNKNOWN",
        "month": month,
        "statistics": monthly,
        "quality_status": quality_status,
        "review_queues": review_queues,
    }


def _iter_content_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    attractions = payload.get("attractions") if isinstance(payload.get("attractions"), list) else []
    festivals = payload.get("festivals") if isinstance(payload.get("festivals"), list) else []
    for row in attractions:
        if isinstance(row, dict):
            result.append(dict(row))
    for row in festivals:
        if isinstance(row, dict):
            row = dict(row)
            row.setdefault("contenttypeid", "15")
            result.append(row)
    return result


def _iter_visitor_statistics(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("visitor_statistics")
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(raw, dict):
        if "monthly_statistics" in raw and isinstance(raw["monthly_statistics"], list):
            return [row for row in raw["monthly_statistics"] if isinstance(row, dict)]
    return []


def _validate_coordinates(raw_lon: Any, raw_lat: Any) -> tuple[bool, float | None, float | None, list[str]]:
    issues: list[str] = []
    try:
        lon = float(raw_lon)
        lat = float(raw_lat)
    except (TypeError, ValueError):
        return False, None, None, ["location_review"]
    if not (KR_BOUNDS["lon_min"] <= lon <= KR_BOUNDS["lon_max"] and KR_BOUNDS["lat_min"] <= lat <= KR_BOUNDS["lat_max"]):
        return False, lon, lat, ["location_review"]
    if lon == 0.0 and lat == 0.0:
        return False, lon, lat, ["location_review"]
    return True, lon, lat, []


def _build_city_id(meta: dict[str, Any], city_name_en: str) -> str:
    city_code = _first_non_empty(str(meta.get("city_id") or ""), str(meta.get("cityCode") or ""))
    if city_code:
        return city_code if city_code.startswith("KR-") else f"KR-{city_code}"
    region = str(meta.get("lDongRegnCd") or "")
    signgu = str(meta.get("lDongSignguCd") or "")
    if region and signgu:
        return f"KR-{region}-{signgu}"
    return f"KR-{_first_non_empty(city_name_en, 'UNKNOWN')}"


def _calc_quality_status(issues: list[str]) -> str:
    if "missing_contentid" in issues or "missing_title" in issues:
        return "failed"
    if issues:
        return "review"
    return "passed"


def _first_non_empty(*values: str) -> str:
    for value in values:
        value = value.strip()
        if value:
            return value
    return ""


def _to_iso_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    if len(value) == 8 and value.isdigit():
        try:
            return datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def _month_to_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "unknown"


def _derive_visit_months(start_iso: str, end_iso: str) -> list[int]:
    if not start_iso or not end_iso:
        return []
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
    except ValueError:
        return []
    months: set[int] = set()
    current = start.replace(day=1)
    while current <= end:
        months.add(current.month)
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return sorted(months)


def as_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)
