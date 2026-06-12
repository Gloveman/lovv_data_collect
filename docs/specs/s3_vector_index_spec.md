# Spec: KR S3 Vector Index 구축 (TourKoreaDomainData → kr-tour-domain-v1)

> Source: DynamoDB `TourKoreaDomainData`(4,334 items, GSI1·GSI2·GSI3 ACTIVE), `s3://lovv-data-pipeline-dev-925273580929/raw/KR/details/20260609/*.json`
> PRD: `docs/s3_vector_index_prd.md` (v0.1.2)
> 기술 계약 정본: 문서 저장소(`00_oh_my_documents`) `docs/08_data_preprocessing/s3_vector_index_plan.md` (v0.3)
> Status: Draft for implementation planning
> Created: 2026-06-11
> Owner role: Spec Agent
> Execution mode: Sequential Mode (인프라 생성·불가역 설정·대량 쓰기 포함)

## Summary

전처리 완료된 DynamoDB `TourKoreaDomainData`를 원천으로, 추천 검색과 RAG 후보 생성을 위한 S3 vector index `kr-tour-domain-v1`을 구축한다. 이 인덱스의 1차 소비자는 `Candidate_Evidence_Agent`(CEA)이며, raw/soft 이중 query channel, theme quota 필터, anchored 검색, DynamoDB 재검증 경로를 지원해야 한다.

인덱스는 파생물이다. 정본은 S3 Raw와 DynamoDB이며, 인덱스는 언제든 전체 재생성 가능해야 한다.

## Goals

1. `lovv-vector-dev` vector bucket과 `kr-tour-domain-v1` index를 1024차원/cosine/non-filterable 4종(`raw_s3_uri`, `ddb_pk`, `ddb_sk`, `embedding_model`)으로 생성한다.
2. GSI3 기반 entity type별 export로 벡터화 대상(`city_metadata`, `attraction`, `restaurant`, `festival`)을 추출하고 수량을 확정한다.
3. entity별 chunk 템플릿(rich embedding_text, restaurant는 DynamoDB `address` 사용 명시)으로 chunk를 생성한다.
4. Titan Text Embeddings V2로 embedding을 생성하고 PutVectors로 upsert한다 (batch ≤ 500, 쓰기 처리량 제한 준수).
5. vector key `{source_type}#{source_id}#{chunk_no}` 3분절과 metadata allowlist(filterable 2KB 예산)를 강제한다.
6. index manifest(`index_text_mode: "rich"` 포함)와 품질/실패 리포트를 산출한다.
7. CEA 질의 패턴 4종(이중 channel, city_discovery 집계, anchored, theme quota)을 검증한다.

## Non-Goals

- Candidate_Evidence_Agent 본체·Scoring Tool 구현
- Planner/Festival_Verifier 구현
- DynamoDB 적재 파이프라인 수정 (`kr_details_pipeline`은 읽기 전용 의존)
- `visitor_statistics`의 개별 벡터화
- JP 인덱스, OpenSearch 연동
- 추천 API/serving 구현

## User Flow

```text
[운영자] index build CLI 실행
→ GSI3 export (entity type별 query, 수량 집계)
→ chunk 생성 (entity별 템플릿, metadata allowlist·2KB 검사)
→ Titan V2 embedding (batch 16~64)
→ PutVectors upsert (batch ≤500, 재시도·실패 격리)
→ manifest·품질 리포트 저장
→ 샘플 QueryVectors 검증 (CEA 질의 패턴)
[CEA(후속)] QueryVectors → ddb_pk/ddb_sk로 DynamoDB 재검증
```

## Requirements

PRD `docs/s3_vector_index_prd.md`의 FR-01~FR-08을 따른다. 요약:

| ID | 요구 |
| --- | --- |
| FR-01 | index 리소스 생성. dimension/metric/non-filterable keys는 생성 후 변경 불가이므로 생성 전 고정 |
| FR-02 | GSI3 export, 전체 scan 금지, `quality_status = passed`만 포함, `visitor_statistics` 제외 |
| FR-03 | rich embedding_text chunk (restaurant는 DynamoDB `address`를 embedding_text에 포함), item당 1 chunk·city 1~3 chunk |
| FR-04 | Titan V2 1024차원, batch 16~64, 실패 격리 |
| FR-05 | PutVectors ≤500/회, 쓰기 처리량(초당 요청 1,000/벡터 2,500) 이내, batch 재시도, metadata 2KB 검사 |
| FR-06 | CEA 질의 패턴(이중 channel, city_discovery, anchored, theme quota, 후보 예산 30) 지원 검증 |
| FR-07 | `place_id = {source_type}#{source_id}` 매핑 계약 (chunk_no 제거) |
| FR-08 | manifest에 entity별 수량·조회 시각·`index_text_mode: "rich"` 기록, 품질 리포트 산출 |

## Acceptance Criteria

PRD AC-01~AC-09와 동일하다. 핵심:

- index가 1024/cosine/non-filterable 4종으로 생성된다.
- vector 수 = chunk 수 = PutVectors 성공 수가 manifest에서 일치한다 (실패 0 목표).
- `visitor_statistics` 개별 벡터가 존재하지 않는다.
- anchored 질의(`city_id = KR-Andong`)에서 타 도시 chunk 0건.
- 샘플 질의 4종(기술 계약 §7.2)과 raw/soft 이중 질의·theme 필터 질의가 유효한 결과를 반환한다.
- 결과의 `ddb_pk`/`ddb_sk`로 DynamoDB 재조회가 성공한다.

## Constraints

- AWS S3 Vectors 제약 (2026-06-10 확인): dimension 1~4,096, filterable metadata 2KB, vector당 키 50, non-filterable 키 index당 10, PutVectors 500, Top-K 100, 쓰기 초당 요청 1,000·벡터 2,500.
- dimension·metric·non-filterable key는 index 생성 후 변경 불가.
- `city_id`는 실데이터 형식 `KR-{CityNameEn}` 고정. 형식 변경은 전체 재색인 사유.
- AWS 자격증명은 `.env`/환경변수로만 주입. 코드·문서에 하드코딩 금지 (root AGENTS.md 환경변수 안전 규칙).
- `s3vectors` IAM 권한은 writer와 reader(CEA) 역할로 분리.
- 기존 `kr_details_pipeline` 코드는 수정하지 않는다 (읽기 참조만).

## Risks

| 위험 | 내용 | 완화 |
| --- | --- | --- |
| 수량 추정 불확실 | entity별 분해(3,814/480)는 추정값 (신뢰도: 중간) | Phase 0에서 GSI3 집계로 확정 후 진행 |
| Terraform S3 Vectors 지원 | provider의 S3 Vectors 리소스 지원이 불완전할 수 있음 (신뢰도: 낮음 — 구현 시점 확인 필요) | 미지원 시 boto3 생성 스크립트로 대체하고 리소스 정의를 코드로 보존 |
| Titan 처리량/비용 | 약 3,900건 embedding 호출 비용·throttling | batch 16~64, 지수 백오프, 실패 격리 |
| Top-K 100 한계 | city_discovery에서 도시별 evidence 부족 가능 | 테마·필터 분할 질의로 보완 (FR-06) |
| chunk 품질 | 요약문 길이·품질 편차 | 샘플 질의 4종 + 수동 spot check |

## Task Breakdown

단계별 상세는 `docs/s3_vector_index_implementation_plan.md`를 따른다. Feature Task 요약:

1. Phase 0 — 사전 확정: GSI3 수량 집계, 인덱스 설정 고정 검토
2. Phase 1 — 인프라: vector bucket·index 생성, IAM 분리
3. Phase 2 — Export 모듈: GSI3 entity type별 export
4. Phase 3 — Chunk builder: 템플릿 4종, metadata allowlist·2KB 검사
5. Phase 4 — Embedding client: Titan V2 batch
6. Phase 5 — Upsert: PutVectors batch·재시도·실패 격리
7. Phase 6 — Manifest·리포트
8. Phase 7 — 검증: 샘플 질의·CEA 질의 패턴·AC 체크리스트

## Verification

- unit test: classifier 제외 규칙(`visitor_statistics`), chunk 템플릿 4종, vector key 3분절·`place_id` 파생, metadata 2KB 검사, batch 분할.
- integration: dev 환경에서 1개 도시(`KR-Andong`) 부분 색인 후 anchored 질의 검증.
- 전체 빌드 후: manifest 수량 일치, 샘플 질의 4종, raw/soft 이중 질의, DynamoDB 재조회 round-trip.
- `pytest` 전체 통과, 실패 리포트 0건 확인.

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
| --- | --- | --- | --- |
| v0.1 | 2026-06-11 | 조동휘 | PRD v0.1.1 기준 Spec 초안 작성 (Sequential Mode, Phase 0~7 Task Breakdown) |
| v0.1.1 | 2026-06-11 | 조동휘 | PRD v0.1.2에 맞춰 restaurant 주소 항목을 DynamoDB 누락이 아닌 chunk 템플릿 계약 보완으로 명확화 |
