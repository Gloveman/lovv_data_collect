# Bedrock Metadata Enrichment — 구현 완료 보고서

**완료 일시:** 2026-06-23
**Spec:** `.kiro/specs/bedrock-metadata-enrichment/`
**테스트 결과:** 185 passed, 0 failed (`uv run python -m pytest src --basetemp .cache\pytest-tmp -p no:cacheprovider`)

---

## 요약

Lovv 여행 데이터 파이프라인에 Bedrock LLM 기반 관광지 메타데이터 보강 및 축제 테마 재분류 기능을 구현했습니다. 총 29개 필수 태스크를 모두 완료하고, 13개 선택적 property-based 테스트가 향후 구현 대상으로 남아있습니다.

---

## 구현 내역

### 1단계: 식당(Restaurant) entity 제거

| 파일 | 변경 내용 |
|------|-----------|
| `src/kr_details_pipeline/domain_preprocess.py` | `DOMAIN_KEYS`에서 restaurant 제거, contenttypeid "39" → `"excluded"` 반환, restaurant 빌드 브랜치 제거, restaurants 버킷 제거 |
| `src/kr_vector_index/export.py` | `VECTORIZABLE_ENTITY_TYPES`에서 restaurant 제거 |
| `src/kr_vector_index/chunks.py` | `build_embedding_text()`, `_type_label()`, `_tags()`에서 restaurant 관련 분기 제거 |
| 테스트 6개 파일 | restaurant 참조를 attraction/festival로 변환 |

### 2단계: 전처리 확장 (원천 분류 코드 보존)

| 파일 | 변경 내용 |
|------|-----------|
| `domain_preprocess.py` | `extract_lcls_systm3()` 함수 추가 — common.lclsSystm3 우선, record fallback |
| `domain_preprocess.py` | `SubtypeMappingResult` dataclass + `map_attraction_subtype()` 결정론적 매핑 |
| `domain_preprocess.py` | `FestivalSourceFields` dataclass + `preserve_festival_source()` 축제 원천 보존 |
| `domain_preprocess.py` | `_build_domain_item()` 통합 — lcls_systm3, source_type, raw_s3_uri, subtype 매핑, 축제 소스 |
| `classification_dict.json` | 19개 코드 매핑 (관광지 13 + 축제 6), version "2026-06-07" |
| `DOMAIN_KEYS` 확장 | attraction: +4 필드, festival: +6 필드, COMMON_KEYS: +3 필드 |

### 3단계: Bedrock 관광지 Enrichment Engine

| 파일 | 변경 내용 |
|------|-----------|
| `src/kr_details_pipeline/enrichment_engine.py` (신규) | 전체 모듈 구현 |
| — | `EnrichmentResult`, `BatchResult` dataclass |
| — | Canonical Taxonomy 상수 (VIBE_TAGS 38개, EXPERIENCE_TAGS 10개, COMPANION_FIT 7개, INDOOR_OUTDOOR 4개) |
| — | `compute_input_hash()` — SHA-256 중복 호출 방지 |
| — | `should_skip_enrichment()` — hash+version+model 일치 시 스킵 |
| — | `build_extraction_prompt()` — 허용 필드만 포함, 12,000자 제한 |
| — | `validate_extracted_metadata()` — 4개 출력 필드 검증, 비정규 태그 제거 |
| — | `enrich_attraction()` — Bedrock converse API 호출, 최대 2회 재시도, 지수 백오프 |
| — | `run_enrichment_batch()` — 500건 초과 시 100건 단위 분할, 장애 격리 |

### 4단계: Bedrock 축제 테마 재분류기

| 파일 | 변경 내용 |
|------|-----------|
| `src/kr_details_pipeline/theme_classifier.py` (신규) | 전체 모듈 구현 |
| — | `ThemeClassificationResult`, `ClassificationBatchResult` dataclass |
| — | `LOVV_THEMES` 6대 테마 상수 |
| — | `compute_festival_input_hash()` — 축제 전용 SHA-256 |
| — | `should_skip_classification()` — 중복 호출 방지 |
| — | `build_festival_prompt()` — 허용 필드만, 분류 규칙 포함 |
| — | `validate_festival_theme_output()` — primary_theme 1개 + theme_tags 1-3개 검증 |
| — | `classify_festival_theme()` — Bedrock 호출, 텍스트 충분성 검사, 실패 시 source_theme 미승격 |
| — | `run_classification_batch()` — 배치 처리, 장애 격리 |

### 5단계: Vector Metadata 확장

| 파일 | 변경 내용 |
|------|-----------|
| `src/kr_vector_index/metadata.py` | `FILTERABLE_METADATA_KEYS` +6 필드, `FORBIDDEN_METADATA_KEYS` 9 필드 |
| — | `build_enriched_metadata()` — status==succeeded 조건부 포함, None/빈값 제거 |
| — | `trim_to_budget()` — 2048 bytes 초과 시 배열 필드 뒤에서 trim |
| `src/kr_vector_index/chunks.py` | `build_chunk()` 통합 — enrichment 필드 병합, 사이즈 준수, fallback 처리 |

### 6단계: 축제 월별 GSI 지원

| 파일 | 변경 내용 |
|------|-----------|
| `domain_preprocess.py` | `build_festival_gsi_sk()` — `FESTIVAL#{month:02d}#{content_id}` 형식 |
| — | festival branch에 `gsi_sk` 필드 통합, DOMAIN_KEYS 추가 |
| `src/kr_details_pipeline/gsi_query.py` (신규) | `query_festivals_by_month()` — GSI 월별 range query + 페이지네이션 + 상태 필터 |

---

## 테스트 커버리지

| 테스트 파일 | 테스트 수 | 범위 |
|------------|----------|------|
| `test_domain_preprocess.py` | 13 | 전처리, 분류, 소스 필드, GSI SK |
| `test_enrichment_engine.py` | 22 | validate_extracted_metadata |
| `test_build_extraction_prompt.py` | 17 | 프롬프트 필드 경계, 길이 제한 |
| `test_enrich_attraction.py` | 21 | Bedrock 호출, 재시도, 스킵, 실패 |
| `test_classify_festival_theme.py` | 19 | 축제 분류, 재시도, 텍스트 충분성 |
| `test_classification_batch.py` | 10 | 배치 처리, 장애 격리 |
| `test_gsi_query.py` | 17 | GSI query 구성, 페이지네이션 |
| `test_metadata.py` | 17 | validate, build_enriched, trim_to_budget |
| `test_chunks.py` | 2 | 결정론적 빌드, 분류 태그 |
| `test_export.py` | 2 | vectorize 필터 |
| `test_vector_index_handler.py` | 3 | 핸들러 통합 |
| `test_upsert.py` | 4 | vector record 빌드 |
| 기타 기존 src 테스트 | 38 | 기존 테스트 유지 |
| **합계** | **185** | |

---

## 미완료 항목 (선택적 — Property-Based Tests)

13개 Hypothesis 기반 property test가 남아있습니다. 이들은 tasks.md에서 `*` 표시된 선택적 태스크입니다:

- Property 1: lcls_systm3 추출 및 폴백
- Property 2, 3: 결정론적 subtype 매핑 + 미매핑 코드 처리
- Property 4: 관광지 프롬프트 필드 경계
- Property 5: Canonical Taxonomy 검증
- Property 6: input_hash 기반 중복 호출 방지
- Property 7: 실패 시 원본 item 보존 불변식
- Property 8: 축제 원천 분류 및 프로그램 보존
- Property 9: 축제 프롬프트 필드 경계
- Property 10: 축제 테마 출력 검증
- Property 11: 축제 재분류 시 원천 분류 보존
- Property 12: Vector metadata 계약
- Property 13: GSI SK 형식과 월 결정
- Property 14: 배치 분할과 장애 격리

이들은 `hypothesis` 라이브러리를 사용하며, 기존 단위 테스트로 커버된 로직의 공식적 정확성 보장을 강화합니다.

---

## 의존성

기존 `pyproject.toml` dev dependencies에 추가 필요:
```toml
[dependency-groups]
dev = [
    "hypothesis>=6.100,<7",  # property-based testing (선택적 테스트용)
]
```

런타임 의존성 추가 없음 — `botocore`는 기존 boto3에 포함.

---

## 알려진 제한사항

1. **Windows tmp_path 권한 이슈**: 기본 Windows temp 경로에서는 `tmp_path` fixture 생성 시 PermissionError가 발생할 수 있다. repo-local `--basetemp .cache\pytest-tmp`와 cacheprovider 비활성화로 회피해 현재 `src` 테스트 185개가 통과했다.
2. **Bedrock 모델 ID**: 현재 `anthropic.claude-3-haiku-20240307-v1:0`로 설정. 실제 배포 시 사용 가능한 모델로 변경 필요.
3. **classification_dict.json**: 19개 코드만 포함. 실 데이터에 맞게 확장 필요.

---

## 다음 단계

1. Property-based 테스트 구현 (선택적, hypothesis 라이브러리 설치 필요)
2. `classification_dict.json` 실제 TourAPI 코드로 확장
3. Bedrock 모델 ID 확정 및 프롬프트 튜닝
4. DynamoDB GSI 인프라 배포 (FestivalMonthIndex)
5. 파이프라인 통합 테스트 (실제 Bedrock 호출 포함)
