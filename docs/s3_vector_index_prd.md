# 로브 (Lovv) KR S3 Vector Index 구축 PRD (Candidate Evidence Agent 검색 요구 기준)

> 문서 버전: v0.1
> 문서 상태: 초안 (Draft)
> 작성일: 2026-06-11
> 작성자: 조동휘
> 범위 한정: **KR S3 vector index(`kr-tour-domain-v1`) 구축과 Candidate_Evidence_Agent 검색 요구 충족**. 제품 전체 PRD 아님
> 입력 문서: 문서 저장소(`00_oh_my_documents`)의 `docs/08_data_preprocessing/s3_vector_index_plan.md`(v0.3), `docs/05_agent_spec/candidate_evidence_agent.md`(v0.1), `docs/04_database_design/04_database_design.md`(§3.4) / 본 저장소의 `docs/reports/korea_data_preprocessing_result_report.md`
> 보조 문서: 본 문서는 실행 단위 PRD다. 인덱스 기술 계약의 정본은 문서 저장소의 `s3_vector_index_plan.md`이며, 본 PRD와 충돌 시 해당 문서의 최신 결정을 우선 확인하고 반영한다.
> 구현 문서: Spec `docs/specs/s3_vector_index_spec.md`, 단계별 Plan `docs/s3_vector_index_implementation_plan.md`

# 1. 개요

## 1.1 목적

본 문서는 한국 데이터 전처리 결과보고서로 확정된 DynamoDB `TourKoreaDomainData`(4,334 items)를 입력으로 **S3 vector index `kr-tour-domain-v1`을 실제 구축**하기 위한 제품 요구사항을 정의한다.

이 인덱스의 1차 소비자는 `Candidate_Evidence_Agent`다. 따라서 본 PRD는 인덱스 생성 계약(`s3_vector_index_plan.md` v0.2)을 **Candidate_Evidence_Agent 명세(v0.1)의 검색·점수화 요구와 1:1로 대조**하고, 대조에서 드러난 공백을 기능 요구사항으로 흡수한다.

## 1.2 배경

- 전처리 결과보고서 기준 KR 40개 도시(강원도·경상북도) 데이터가 `TourKoreaDomainData`에 적재 완료되었고 GSI 3종이 `ACTIVE` 상태다.
- `Candidate_Evidence_Agent`는 기존 `Polymorphic_Retriever_Agent`/`Ranker_Agent`를 통합한 상세 정본으로, 런타임에 원본을 임베딩하지 않고 **사전 구축된 S3 vector index**를 전제한다(동 문서 §9).
- 인덱스가 없으면 `city_discovery`/`anchored_place_search` 두 검색 모드 모두 동작할 수 없으므로, Agent 구현 이전에 인덱스가 먼저 존재해야 한다.

## 1.3 범위

| 구분 | 내용 |
| --- | --- |
| **구현 대상(신규)** | ① `lovv-vector-dev` vector bucket과 `kr-tour-domain-v1` index 생성, ② GSI3 기반 export → chunk → embedding → PutVectors 파이프라인, ③ Candidate_Evidence_Agent 질의 패턴(이중 query channel, theme quota, anchor filter)을 지원하는 metadata 계약 적용, ④ index manifest·품질/실패 리포트 |
| 제외 | Candidate_Evidence_Agent 자체 구현, Scoring Tool 구현, Planner/Festival_Verifier, DynamoDB 적재 파이프라인(완료됨), JP 인덱스, OpenSearch 연동 |
| 전제 | `TourKoreaDomainData` 적재 완료 상태(결과보고서 기준)를 변경하지 않는다 |

## 1.4 용어

| 용어 | 정의 |
| --- | --- |
| CEA | `Candidate_Evidence_Agent`. 도시/장소 후보 검색·점수화·패키징 담당 |
| raw channel | `cleaned_raw_query` 기반 의미 검색 채널 |
| soft channel | `soft_preference_query` 기반 분위기·선호 검색 채널 |
| rich embedding_text | 장소명·도시명·테마·유형·주소·메뉴·요약·파생 태그를 포함한 document-side 임베딩 텍스트(CEA §9) |
| anchored 검색 | `destinationId`가 주어져 특정 도시 내부만 검색하는 모드 |

# 2. Candidate Evidence Agent 요구 대조

## 2.1 검색 모드별 인덱스 요구

| CEA 검색 모드 | 인덱스에 요구되는 동작 |
| --- | --- |
| `city_discovery` | `country`(+`province`, 월/테마) 필터로 장소 chunk를 검색한 뒤, 결과의 `city_id` metadata로 도시 단위 집계(`semantic_evidence`, `theme_coverage`)가 가능해야 함 |
| `anchored_place_search` | `city_id` 필터로 지정 도시 내부 후보만 반환. 타 도시 chunk가 섞이면 CEA가 `anchor_violation`으로 결과를 폐기하므로 필터 정확성이 필수 |

## 2.2 요구 ↔ 인덱스 계약 대조표

CEA v0.1의 요구를 `s3_vector_index_plan.md` v0.2 계약과 대조한 결과다.

| # | CEA 요구 (근거 절) | 인덱스 계약 v0.2 | 판정 | 조치 |
| --- | --- | --- | --- | --- |
| 1 | raw/soft 이중 query channel (§3, §8.2 `raw_similarity`·`soft_similarity`) | 단일 index에 QueryVectors 2회 호출로 대응 가능. 스키마 변경 불필요 | 충족 | FR-06에 이중 질의 검증 포함 |
| 2 | rich embedding_text: 장소명·도시명·테마·유형·주소·메뉴·원본 설명·파생 태그 (§9) | DynamoDB restaurant item에는 `address`가 적재되어 있으나, §5.2 restaurant chunk 템플릿이 해당 `address`를 embedding_text에 포함한다는 계약이 명확하지 않음 | **공백** | FR-03에서 restaurant chunk가 DynamoDB `address`를 사용하도록 명시 |
| 3 | `city_discovery` 도시 집계 (§4, §8.1) | `city_id`·`province` filterable metadata로 집계 가능 | 충족 | — |
| 4 | anchored 검색·`anchor_violation` 방지 (§4, §11) | `city_id` filterable | 충족 | AC-05 검증 |
| 5 | theme quota: `active_required_themes`별 minimum quota (§7) | `theme_tags` list filterable → 테마별 필터 질의로 quota 충족 가능 | 충족 | FR-06에 테마별 질의 포함 |
| 6 | `distance_penalty`·`local_distance_penalty` (§8) | `latitude`/`longitude` number metadata (v0.2 추가) | 충족 | — |
| 7 | `congestion_penalty` (§8.1) | vector metadata에 혼잡도 수치 없음. city chunk 텍스트에만 반영 | 의도된 분리 | 수치 계산은 DynamoDB `visitor_statistics` 재조회 책임으로 명시 (§2.3) |
| 8 | `source_quality_score`: 근거 필드 충분성 (§8.2) | metadata 아님 | 의도된 분리 | `ddb_pk`/`ddb_sk` 재조회로 CEA가 산정 (§2.3) |
| 9 | `includeFestivals` 분기 (§3) | `entity_type` filterable | 충족 | — |
| 10 | 후보 예산 최대 30(primary 18 + reserve 12) (§6) | QueryVectors Top-K 최대 100 | 충족 | 단 `city_discovery`는 도시별 evidence 확보를 위해 K 상향 또는 테마·도시 필터 반복 질의 필요. FR-06 |
| 11 | `place_id` 후보 식별 (§5.3) | vector key 3분절 `{source_type}#{source_id}#{chunk_no}` | 계약 필요 | FR-07에서 vector key ↔ `place_id` 매핑 규칙 정의 |
| 12 | `retrieval_audit.index_text_mode = "rich"` (§10.2) | manifest에 기록 항목 없음 | **공백** | FR-08에서 manifest에 `index_text_mode` 기록 |
| 13 | DynamoDB 재검증 (§9 전제, plan §7.2) | `ddb_pk`/`ddb_sk` non-filterable로 결과에 포함 | 충족 | — |

## 2.3 인덱스 책임과 DynamoDB 재조회 책임의 경계

CEA의 점수 항목 중 다음은 **의도적으로 vector metadata에 두지 않는다**. filterable 2KB 예산을 지키고, 시점 민감 데이터(혼잡도·운영 상태)가 인덱스에 박제되는 것을 막기 위함이다.

| 점수 항목 | 데이터 원천 | 접근 경로 |
| --- | --- | --- |
| `congestion_penalty` | `visitor_statistics` (DynamoDB) | `PK = CITY#{city_name_en}` 또는 GSI3 query |
| `source_quality_score` | 정규화 item 필드 충분성 | vector 결과의 `ddb_pk`/`ddb_sk` 재조회 |
| 축제 날짜·운영 여부 확정 | DynamoDB + Festival_Verifier | 동일 재조회 경로 |

## 2.4 식별자 정합성 주의

CEA v0.1 §5의 예시는 `"city_id": "Yeongdeok"`으로 표기되어 있으나, 실데이터 확정 형식은 **`KR-{CityNameEn}`(예: `KR-Yeongdeok`)**이다. 본 PRD와 인덱스는 실데이터 형식을 기준으로 하며, CEA 문서 예시 표기는 해당 문서 차기 개정 시 정정 대상이다(본 PRD는 CEA 문서를 수정하지 않는다).

# 3. 기능 요구사항

## FR-01 인덱스 리소스 생성

- `lovv-vector-dev` vector bucket과 `kr-tour-domain-v1` index를 생성한다.
- dimension 1024, metric cosine, non-filterable keys `raw_s3_uri`·`ddb_pk`·`ddb_sk`·`embedding_model` 4종으로 고정한다. 이 값들은 생성 후 변경 불가하므로 생성 전 본 표 기준으로 확정한다.

## FR-02 원천 export

- 전체 scan을 금지하고 GSI3 entity type별 query로 export한다.
- export 시 entity type별 수량을 집계해 plan §2.3의 추정값(벡터화 대상 약 3,854)을 확정치로 대체한다.
- `quality_status = passed` 등 서비스 노출 가능 상태만 대상에 포함하고, `visitor_statistics`(추정 480)는 개별 벡터화에서 제외한다.

## FR-03 chunk 생성 (rich embedding_text)

- `s3_vector_index_plan.md` §5.2 템플릿을 기준으로 하되, CEA §9의 rich embedding_text 필드 목록을 충족하도록 다음 매핑을 보장한다.

| rich 필드 (CEA §9) | city | attraction | restaurant | festival |
| --- | --- | --- | --- | --- |
| 장소명/도시명 | ✓ | ✓ | ✓ | ✓ |
| 테마 | ✓ | ✓ | 음식 카테고리 | ✓ |
| 장소 유형 | `[도시]` | `[관광지]` | `[음식점]` | `[축제]` |
| 주소 | 행정구역 | ✓ | **추가 필요** | 장소(venue) |
| 대표메뉴/취급메뉴 | — | — | ✓ | — |
| 원본 설명(요약) | ✓ | ✓ | ✓ | ✓ |
| 파생 태그 | 추천 월·통계 요약 | 계절·추천 월 | 운영·휴무 | 계절·방문 월 |

- **restaurant chunk 템플릿은 DynamoDB에 적재된 `address` 값을 embedding_text에 포함한다** (대조표 #2 공백 해소). 이는 DynamoDB restaurant item의 주소 누락을 의미하지 않으며, S3 Vector용 chunk 생성 계약의 명시 보완이다. 이 변경은 `s3_vector_index_plan.md` §5.2에도 반영한다.
- item 1개당 기본 1 chunk, city는 방문 통계 요약·대표 관광지/축제를 포함해 1~3 chunk로 생성한다.

## FR-04 embedding 생성

- Amazon Titan Text Embeddings V2(`amazon.titan-embed-text-v2:0`), 출력 1024차원으로 생성한다.
- batch는 16~64 texts 단위로 하고, 실패 record는 격리 후 재시도한다.

## FR-05 PutVectors upsert

- 1회 최대 500 vectors, index당 쓰기 처리량(초당 요청 1,000 / 벡터 2,500) 이내로 upsert한다.
- PutVectors는 batch 원자성이 없으므로 실패 시 batch 단위 재시도하고, 반복 실패 레코드만 `failed/KR/s3-vector/{yyyymmdd}/failed_records.jsonl`로 분리한다.
- vector key는 `{source_type}#{source_id}#{chunk_no}` 3분절, metadata는 plan §4.3 allowlist만 사용하며 filterable 2KB 예산 검사를 통과해야 한다.

## FR-06 CEA 질의 패턴 지원 검증

구축 완료 전 다음 질의 패턴이 동작함을 검증한다.

| 패턴 | 내용 |
| --- | --- |
| 이중 channel | 동일 필터로 raw query·soft query 각 1회 QueryVectors 호출, 두 결과 모두 유효 |
| city_discovery | `country = KR` (+월/테마 필터) Top-K 질의 결과를 `city_id`로 group-by하여 도시별 evidence 집계 가능 |
| anchored | `city_id = KR-{CityNameEn}` 필터 결과에 타 도시 chunk 0건 (`anchor_violation` 방지) |
| theme quota | `theme_tags` 필터로 테마별 질의 시 테마당 후보 확보 가능 (CEA §7 quota 산식 전제: 예: 18후보·2테마 → 테마당 최소 5) |
| 후보 예산 | `4d3n` 기준 total 30 후보를 Top-K ≤ 100 내에서 확보 가능 |

## FR-07 vector key ↔ place_id 매핑 계약

- CEA의 `place_id`는 vector key에서 파생한다: `place_id = {source_type}#{source_id}` (chunk_no 제거). 동일 장소의 복수 chunk는 동일 `place_id`로 집계한다.
- CEA 출력 예시의 `P_001` 같은 값은 패키지 내부 별칭이며, 인덱스 계약 식별자는 본 매핑을 따른다.

## FR-08 manifest·리포트

- index manifest(`processed/KR/s3-vector/manifests/{yyyymmdd}/kr-tour-domain-v1.json`)에 entity type별 원천 수·chunk 수·vector 성공 수·원천 조회 시각, 그리고 **`index_text_mode: "rich"`**를 기록한다 (CEA `retrieval_audit` 대응).
- 품질 리포트(`quality/KR/s3-vector/{yyyymmdd}/summary.json`)에 원천 수·chunk 수·vector 성공 수·실패 수를 기록한다.

# 4. 비기능 요구사항

| 항목 | 요구 |
| --- | --- |
| AWS 제약 준수 | index당 2B vectors, dimension 1~4,096, metadata 40KB(키 50), filterable 2KB, non-filterable 키 10, PutVectors 500, Top-K 100 (2026-06-10 확인 기준) |
| 재현성 | 인덱스는 파생물. S3 Raw + DynamoDB만으로 전체 재생성 가능해야 하며 수작업 보정 금지 |
| 버전 전환 | 재색인은 `kr-tour-domain-v2` 신규 생성 후 검증 통과 시 라우팅 전환, 롤백은 라우팅 복귀 |
| 권한 분리 | `s3vectors:*`는 index writer와 Retriever(CEA) 역할로 분리. CEA는 Query 계열 권한만 보유 |
| 개인정보 | 사용자 ID, 대화 전문, 비공개 운영 메모를 chunk text·metadata에 저장하지 않음 |

# 5. 수용 기준 (체크리스트)

- [ ] AC-01: `kr-tour-domain-v1`이 1024/cosine/non-filterable 4종으로 생성되었는가?
- [ ] AC-02: GSI3 집계로 entity type별 수량이 확정되고, vector 수 = chunk 수 = PutVectors 성공 수가 manifest에서 일치하는가? (실패 0 목표)
- [ ] AC-03: `visitor_statistics`가 개별 벡터로 존재하지 않고 city chunk 보조 문맥으로만 반영되었는가?
- [ ] AC-04: restaurant chunk에 주소가 포함되어 rich embedding_text 필드 목록(§3 FR-03 매핑표)을 충족하는가?
- [ ] AC-05: anchored 질의(`city_id = KR-Andong` 등)에서 타 도시 chunk가 0건인가?
- [ ] AC-06: 샘플 질의 4종(plan §7.2)이 기대 결과를 반환하는가?
- [ ] AC-07: raw/soft 이중 질의와 theme_tags 필터 질의가 모두 유효한 결과를 반환하는가?
- [ ] AC-08: 결과의 `ddb_pk`/`ddb_sk`로 DynamoDB 재조회가 성공하는가? (CEA 재검증 경로)
- [ ] AC-09: manifest에 `index_text_mode`와 entity type별 수량·조회 시각이 기록되었는가?

# 6. 범위 밖 (후속/타 문서 소관)

| 항목 | 소관 |
| --- | --- |
| CEA 본체·Scoring Tool 구현 | `05_agent_spec/candidate_evidence_agent.md` |
| CEA 문서의 `city_id` 예시 표기 정정 | `candidate_evidence_agent.md` 차기 개정 |
| 축제 날짜 검증 | `Festival_Verifier_Agent` |
| JP 인덱스(`jp-tour-domain-v1`) | JP 전처리 완료 후 별도 PRD |
| OpenSearch Serverless 연동 | 고QPS 단계 검토 |

# 7. 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
| --- | --- | --- | --- |
| v0.1.2 | 2026-06-11 | 조동휘 | 실제 DynamoDB restaurant item에 `address`가 적재되어 있음을 확인하고, 주소 이슈를 DynamoDB 누락이 아닌 S3 Vector chunk 템플릿 계약 보완으로 명확화 |
| v0.1.1 | 2026-06-11 | 조동휘 | 문서 저장소(`00_oh_my_documents/docs/98_prd/`)에서 구현 저장소(`02_lovv_data_collect/docs/`)로 이동, 입력 문서 경로 보정, Spec·Plan 링크 추가 |
| v0.1 | 2026-06-11 | 조동휘 | CEA v0.1 요구 대조표 기반 KR S3 vector index 구축 PRD 초안 작성. 공백 2건(restaurant 주소, manifest `index_text_mode`)을 FR로 흡수, `place_id` 매핑·책임 경계 정의 |
