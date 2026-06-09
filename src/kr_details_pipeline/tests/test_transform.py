"""Tests for KR raw-to-processed transformation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from kr_details_pipeline import transform


class TransformTest(unittest.TestCase):
    def test_transform_attraction_and_festival(self) -> None:
        payload = {
            "meta": {
                "city_name_en": "ANDONG",
                "city_name_ko": "안동시",
                "province": "경상북도",
                "lDongRegnCd": "47",
                "lDongSignguCd": "001",
            },
            "attractions": [
                {
                    "contentid": "1001",
                    "title": "축제광장",
                    "mapx": "128.6",
                    "mapy": "36.5",
                    "_assigned_theme": "tour",
                    "detail": {
                        "common": {"overview": "<p>good</p>", "tel": "010-111"},
                        "intro": {"addr1": "test road"},
                    },
                    "contenttypeid": "12",
                }
            ],
            "festivals": [
                {
                    "contentid": "2002",
                    "title": "가을축제",
                    "mapx": "128.7",
                    "mapy": "36.4",
                    "detail": {"intro": {"eventstartdate": "20260101", "eventenddate": "20260103"}},
                    "contenttypeid": "15",
                }
            ],
            "visitor_statistics": [{"month": "202601"}],
        }

        result = transform.transform_raw_city(payload, source_key="raw-key")

        self.assertEqual("KR-47-001", result.city_id)
        self.assertEqual(2, len(result.passed))
        self.assertEqual(1, len(result.review))
        self.assertEqual(0, len(result.failed))
        self.assertEqual("ATTRACTION#1001", result.passed[0]["SK"])
        self.assertEqual("FESTIVAL#2002", result.review[0]["SK"])

    def test_transform_rejects_invalid_coordinate(self) -> None:
        payload = {
            "meta": {"city_name_en": "INVALIDCITY"},
            "attractions": [{"contentid": "1", "title": "bad", "mapx": "0", "mapy": "0"}],
        }

        result = transform.transform_raw_city(payload, source_key="raw-key")
        self.assertEqual("review", result.review[0]["quality_status"])
        self.assertIn("location_review", result.review[0]["review_queues"])

    def test_derive_visit_months(self) -> None:
        months = transform._derive_visit_months("2026-01-31", "2026-03-02")
        self.assertEqual([1, 2, 3], months)

    def test_serialize_payload(self) -> None:
        payload = {
            "meta": {"city_name_en": "A"},
            "attractions": [{"contentid": "1", "title": "x"}],
        }
        result = {"a": 1}
        with tempfile.TemporaryDirectory(dir=".") as _:
            pass
        text = transform.as_json(result)
        self.assertEqual("{\n  \"a\": 1\n}", text)

    def test_visitor_month_format_variants(self) -> None:
        city = transform.build_city_record({
            "meta": {
                "city_name_en": "Andong",
                "city_name_ko": "안동시",
                "lDongRegnCd": "47",
                "lDongSignguCd": "001",
            }
        })
        stat = transform.transform_visitor_statistic({"month": "2025-01"}, city)
        self.assertEqual("passed", stat["quality_status"])
        self.assertEqual("STAT#202501", stat["SK"])
        self.assertEqual("202501", stat["month"])


if __name__ == "__main__":
    unittest.main()
