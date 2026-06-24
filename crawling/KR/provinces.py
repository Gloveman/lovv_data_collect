"""
South Korea province reference data.

This file owns province lookup, detection, and English/ID translation
mapping for all 17 Korean metropolitan cities and provinces.
"""

from __future__ import annotations

import re
from typing import Final

from crawling.KR.models import ProvinceReference

PROVINCES: Final[tuple[ProvinceReference, ...]] = (
    ProvinceReference("KR-11", "서울특별시", "Seoul", "Capital"),
    ProvinceReference("KR-26", "부산광역시", "Busan", "Yeongnam"),
    ProvinceReference("KR-27", "대구광역시", "Daegu", "Yeongnam"),
    ProvinceReference("KR-28", "인천광역시", "Incheon", "Capital"),
    ProvinceReference("KR-29", "광주광역시", "Gwangju", "Honam"),
    ProvinceReference("KR-30", "대전광역시", "Daejeon", "Chungcheong"),
    ProvinceReference("KR-31", "울산광역시", "Ulsan", "Yeongnam"),
    ProvinceReference("KR-36", "세종특별자치시", "Sejong", "Chungcheong"),
    ProvinceReference("KR-41", "경기도", "Gyeonggi-do", "Capital"),
    ProvinceReference("KR-42", "강원특별자치도", "Gangwon State", "Gangwon"),
    ProvinceReference("KR-43", "충청북도", "Chungcheongbuk-do", "Chungcheong"),
    ProvinceReference("KR-44", "충청남도", "Chungcheongnam-do", "Chungcheong"),
    ProvinceReference("KR-45", "전북특별자치도", "Jeonbuk State", "Honam"),
    ProvinceReference("KR-46", "전라남도", "Jeollanam-do", "Honam"),
    ProvinceReference("KR-47", "경상북도", "Gyeongsangbuk-do", "Yeongnam"),
    ProvinceReference("KR-48", "경상남도", "Gyeongsangnam-do", "Yeongnam"),
    ProvinceReference("KR-50", "제주특별자치도", "Jeju", "Jeju"),
)

# Pre-defined mapping of Korean municipality names to their English romanized names
# and unique IDs to avoid scraping English/Japanese Wikipedia pages.
MUNICIPALITY_EN_MAP: Final[dict[str, str]] = {
    # Gangwon-do (KR-42)
    "춘천시": "CHUNCHEON",
    "원주시": "WONJU",
    "강릉시": "GANGNEUNG",
    "동해시": "DONGHAE",
    "태백시": "TAEBAEK",
    "속초시": "SOKCHO",
    "삼척시": "SAMCHEOK",
    "홍천군": "HONGCHEON",
    "횡성군": "HOENGSEONG",
    "영월군": "YEONGWOL",
    "평창군": "PYEONGCHANG",
    "정선군": "JEONGSEON",
    "철원군": "CHEORWON",
    "철원군 (대한민국)": "CHEORWON",
    "화천군": "HWACHEON",
    "양구군": "YANGGU",
    "인제군": "INJE",
    "고성군": "GOSEONG-GANGWON",
    "고성군 (강원특별자치도)": "GOSEONG-GANGWON",
    "양양군": "YANGYANG",
    # Gyeongszangbuk-do (KR-47)
    "포항시": "POHANG",
    "경주시": "GYEONGJU",
    "김천시": "GIMCHEON",
    "안동시": "ANDONG",
    "구미시": "GUMI",
    "영주시": "YEONGJU",
    "영천시": "YEONGCHEON",
    "상주시": "SANGJU",
    "문경시": "MUNGYEONG",
    "경산시": "GYEONGSAN",
    "의성군": "UISEONG",
    "청송군": "CHEONGSONG",
    "영양군": "YEONGYANG",
    "영덕군": "YEONGDEOK",
    "청도군": "CHEONGDO",
    "고령군": "GORYEONG",
    "성주군": "SEONGJU",
    "칠곡군": "CHILGOK",
    "예천군": "YECHEON",
    "봉화군": "BONGHWA",
    "울진군": "ULJIN",
    "울릉군": "ULLEUNG",
}


def detect_province(texts: list[str]) -> ProvinceReference | None:
    haystack = "\n".join(texts)
    for province in PROVINCES:
        if (
            province.name_ko in haystack
            or re.search(
                rf"\b{re.escape(province.name_en.replace('-do', ''))}\b",
                haystack,
                re.IGNORECASE,
            )
        ):
            return province
    return None


def find_province(prefecture_id: str) -> ProvinceReference | None:
    for province in PROVINCES:
        if province.prefecture_id == prefecture_id:
            return province
    return None
