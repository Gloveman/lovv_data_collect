# KR S3 Vector Index 단계별 구현 Plan

> Spec: `docs/specs/s3_vector_index_spec.md` (v0.1)
> PRD: `docs/s3_vector_index_prd.md` (v0.1.2)
> Execution mode: Sequential Mode — Phase 순서대로 진행하고, 각 Task 완료 시 Review 후 다음으로 이동한다.
> 작성일: 2026-06-11
> 작성자: 조동휘

## 진행 원칙

- Phase는 순서 의존이다. Phase N의 완료 기준을 통과하기 전에 Phase N+1을 시작하지 않는다.
- 신규 코드는 `src/kr_vector_index/` 모듈에 둔다. `src/kr_details_pipeline/`은 읽기 참조만 한다.
- 커밋은 Subtask 단위, Conventional Commits 1.0.0을 따른다 (`docs/agents/commit-convention.md`).
- 자격증명은 `.env`로만 주입하고 `.env.example`에 더미 구조만 추가한다.

## 모듈 구성 (목표)

```text
src/kr_vector_index/
├── __init__.py
├── cli.py            # build/verify/partial-reindex 진입점
├── export.py         # GSI3 entity type별 export, 수량 집계
├── chunks.py         # entity별 chunk 템플릿, vector key/place_id 계약
├── metadata.py       # metadata allowlist, 2KB 예산 검사
├── embed.py          # Titan V2 batch embedding client
├── upsert.py         # PutVectors batch, 재시도, 실패 격리
├── manifest.py       # index manifest, 품질/실패 리포트
└── tests/
```

---

## Phase 0 — 사전 확정 (수량·설정 고정)

### Task: GSI3 entity type별 수량 집계

- Purpose: PRD §2.3의 추정값(벡터화 대상 약 3,854)을 실측으로 확정해 이후 모든 검증 기준치를 고정한다.
- Scope: GSI3 query로 entity type별 item 수 집계 스크립트. 인덱스 생성·쓰기는 하지 않는다.
- Dependencies: 없음 (DynamoDB 읽기 권한만 필요).
- Context Budget:
  - Must read: PRD §2.3·FR-02, 기술 계약 §3.2.
  - Must inspect: `src/kr_details_pipeline/load.py`의 GSI 키 구조.
  - Do not read: `.env`, `terraform.tfstate`.
- Acceptance Criteria: entity type별 수량과 합계(=4,334)가 기록되고, `visitor_statistics` 수가 분리 확인된다.
- Verification: 수동 실행 결과를 `docs/reports/`에 기록. 합계 4,334 일치 확인.

### Task: 인덱스 불가역 설정 고정 검토

- Purpose: dimension/metric/non-filterable key는 생성 후 변경 불가이므로 생성 전 마지막 검토를 거친다.
- Scope: 1024/cosine/non-filterable 4종(`raw_s3_uri`, `ddb_pk`, `ddb_sk`, `embedding_model`) 설정값을 코드 상수로 고정. AWS 제약 문서 재확인.
- Dependencies: 수량 집계 완료.
- Context Budget:
  - Must read: PRD FR-01, 기술 계약 §3.1·§10.
- Acceptance Criteria: 설정 상수 모듈이 존재하고 사용자 승인(검토 통과)을 받았다.
- Verification: 설정값 단위 테스트 (상수 ↔ Spec 표 일치).

## Phase 1 — 인프라 (vector bucket·index·IAM)

### Task: vector bucket·index 생성

- Purpose: `lovv-vector-dev` bucket과 `kr-tour-domain-v1` index를 생성한다.
- Scope: Terraform 리소스 정의 우선. provider가 S3 Vectors를 지원하지 않으면 boto3 생성 스크립트(`infrastructure/` 보관)로 대체. 생성 결과 확인 포함.
- Dependencies: Phase 0 완료.
- Context Budget:
  - Must read: Spec Constraints, `infrastructure/terraform/README.md`.
  - Conditional read: `infrastructure/terraform/main.tf` (기존 패턴 참조).
  - Do not read: `terraform.tfstate` 내용 전문.
- Acceptance Criteria: AC-01 — index가 1024/cosine/non-filterable 4종으로 생성됨을 describe 호출로 확인.
- Verification: `GetIndex`(또는 동등 API) 응답 캡처를 리포트에 기록.

### Task: IAM 권한 분리

- Purpose: writer(빌드 파이프라인)와 reader(CEA)의 `s3vectors` 권한을 분리한다.
- Scope: writer role(Put/Delete/Query), reader role(Query 계열만) 정책 정의.
- Dependencies: bucket·index 생성.
- Context Budget:
  - Must read: PRD §4 권한 분리, 기술 계약 §8.
- Acceptance Criteria: reader 자격으로 PutVectors가 거부되고 QueryVectors는 허용된다.
- Verification: 권한 시뮬레이션 또는 dev 계정 실호출 확인.

## Phase 2 — Export 모듈

### Task: GSI3 entity type별 export 구현

- Purpose: 전체 scan 없이 벡터화 대상 item을 entity type별로 추출한다.
- Scope: `export.py` — GSI3 query, pagination, `quality_status` 필터, `visitor_statistics` 제외, 도시 단위 부분 export(`PK = CITY#{city_name_en}`) 지원.
- Dependencies: Phase 0 수량 집계 (기준치).
- Context Budget:
  - Must read: PRD FR-02, 기술 계약 §3.2.
  - Must inspect: `src/kr_details_pipeline/load.py`·`domain_preprocess.py`의 item 필드 구조.
- Acceptance Criteria: export 수가 Phase 0 집계와 일치하고, 제외 대상이 결과에 없다.
- Verification: unit test — entity type 필터·제외 규칙·pagination. 통합 — 1개 도시 export 실측.

## Phase 3 — Chunk builder

### Task: entity별 chunk 템플릿 구현

- Purpose: rich embedding_text 계약(CEA §9 필드 매핑)대로 검색 문서를 만든다.
- Scope: `chunks.py` — city(1~3 chunk, 방문 통계 요약 포함)·attraction·restaurant(DynamoDB `address`를 embedding_text에 포함)·festival 템플릿, vector key 3분절 생성, `place_id` 파생 규칙.
- Dependencies: Phase 2 export 구현.
- Context Budget:
  - Must read: PRD FR-03·FR-07, 기술 계약 §4.1·§5.
  - Do not read: AWS SDK 문서 (이 Task는 순수 텍스트 변환).
- Acceptance Criteria: AC-04 — restaurant chunk가 DynamoDB `address`를 embedding_text에 포함. 동일 item 재실행 시 동일 vector key 생성(결정론).
- Verification: unit test — 템플릿 4종 출력, key/place_id 계약, 누락 필드 처리.

### Task: metadata allowlist·2KB 예산 검사

- Purpose: filterable 2KB·키 수 제한 위반 vector가 생성되지 않도록 사전 차단한다.
- Scope: `metadata.py` — allowlist 14종(filterable) + 4종(non-filterable), 직렬화 크기 검사, 위반 시 실패 격리 대상으로 라우팅.
- Dependencies: chunk 템플릿 구현.
- Context Budget:
  - Must read: 기술 계약 §4.2·§4.3.
- Acceptance Criteria: allowlist 외 키가 포함된 입력이 거부되고, 2KB 초과 metadata가 실패로 분류된다.
- Verification: unit test — 허용/초과/비허용 키 케이스.

## Phase 4 — Embedding client

### Task: Titan V2 batch embedding

- Purpose: chunk 텍스트를 1024차원 벡터로 변환한다.
- Scope: `embed.py` — `amazon.titan-embed-text-v2:0` 호출, batch 16~64, 지수 백오프 재시도, 실패 record 격리.
- Dependencies: Phase 3 완료.
- Context Budget:
  - Must read: PRD FR-04.
  - Do not read: `.env` (자격증명은 환경변수 주입 전제).
- Acceptance Criteria: 출력 차원이 1024로 검증되고, throttling 시 백오프 후 재시도된다.
- Verification: unit test — mock 응답 차원 검사·재시도 경로. 통합 — 소량 실호출로 차원 확인.

## Phase 5 — Upsert

### Task: PutVectors batch upsert·실패 격리

- Purpose: 생성된 vector를 인덱스에 안전하게 적재한다.
- Scope: `upsert.py` — batch ≤500, 쓰기 처리량(초당 요청 1,000/벡터 2,500) 제한 준수, batch 단위 재시도(원자성 없음 전제), 반복 실패 레코드 `failed/KR/s3-vector/{yyyymmdd}/failed_records.jsonl` 기록. 부분 재색인용 vector id prefix 삭제 지원.
- Dependencies: Phase 4 완료, Phase 1 인프라.
- Context Budget:
  - Must read: PRD FR-05, 기술 계약 §6.2·§8.
- Acceptance Criteria: 실패 batch가 재시도되고, 반복 실패만 실패 리포트로 분리된다. PutVectors 성공 수가 입력 chunk 수와 일치한다.
- Verification: unit test — batch 분할·재시도·격리. 통합 — 1개 도시 upsert 후 수량 확인.

## Phase 6 — Manifest·리포트

### Task: index manifest·품질 리포트 산출

- Purpose: 색인 시점 스냅샷을 자체 보존하고 CEA `retrieval_audit` 요구를 충족한다.
- Scope: `manifest.py` — entity type별 원천 수·chunk 수·vector 성공 수·원천 조회 시각·`index_text_mode: "rich"` 기록, `quality/KR/s3-vector/{yyyymmdd}/summary.json` 산출.
- Dependencies: Phase 5 완료.
- Context Budget:
  - Must read: PRD FR-08, 기술 계약 §6.3.
  - Must inspect: `src/kr_details_pipeline/manifest.py` (기존 manifest 패턴 재사용).
- Acceptance Criteria: AC-02·AC-09 — manifest 수량 3자 일치(원천=chunk=vector 성공), `index_text_mode` 존재.
- Verification: unit test — manifest schema. 통합 — 실제 빌드 산출물 검사.

## Phase 7 — 전체 빌드·검증

### Task: 전체 색인 실행

- Purpose: KR 40개 도시 전체를 색인한다.
- Scope: `cli.py` build 명령으로 전체 파이프라인 실행. 실패 0 목표.
- Dependencies: Phase 1~6 전부.
- Context Budget:
  - Must read: Spec Verification 절.
- Acceptance Criteria: AC-02 수량 일치, AC-03 `visitor_statistics` 벡터 부재, 실패 리포트 0건.
- Verification: manifest·품질 리포트 검사.

### Task: CEA 질의 패턴 검증

- Purpose: 인덱스가 1차 소비자(CEA)의 검색 요구를 실제로 충족하는지 확인한다.
- Scope: 샘플 질의 4종(기술 계약 §7.2), raw/soft 이중 질의, anchored 질의(`city_id = KR-Andong` 타 도시 0건), `theme_tags` 필터 질의, `ddb_pk`/`ddb_sk` DynamoDB round-trip.
- Dependencies: 전체 색인 완료.
- Context Budget:
  - Must read: PRD FR-06·§2.2 대조표, CEA 명세 §3~§7 (문서 저장소).
- Acceptance Criteria: AC-05~AC-08 전부 통과.
- Verification: 질의별 Top-K 결과를 검증 리포트로 `docs/reports/`에 저장.

---

## 완료 게이트 요약

| Phase | 게이트 |
| --- | --- |
| 0 | 수량 확정 + 불가역 설정 사용자 승인 |
| 1 | AC-01 (index 설정 확인) + IAM 분리 확인 |
| 2 | export 수 = Phase 0 집계 |
| 3 | AC-04 + key 결정론 테스트 통과 |
| 4 | 1024차원 검증 |
| 5 | upsert 수량 일치 + 실패 격리 동작 |
| 6 | AC-02·AC-09 |
| 7 | AC-03·AC-05~AC-08 + 검증 리포트 저장 |

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
| --- | --- | --- | --- |
| v0.1.1 | 2026-06-11 | 조동휘 | PRD v0.1.2에 맞춰 restaurant 주소 항목을 DynamoDB 누락이 아닌 chunk 템플릿 계약 보완으로 명확화 |
| v0.1 | 2026-06-11 | 조동휘 | Spec v0.1 기준 Phase 0~7 단계별 구현 Plan 초안 작성 |
