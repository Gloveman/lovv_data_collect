# 작업 결과 보고서

## 1. 요청 반영 범위
- GitHub 저장소: `02_lovv_data_collect`
- 기준 날짜: `2026-06-10` 기준
- 단계 요약: AWS 인프라 구축(Phase 0) + KR 원천 수집/전처리 적재 경로 정비(Phase 1 1차 기준) 완료

## 2. 이번 작업 결과 요약
### 2.1 인프라(IaC) 정비
- `infrastructure/terraform/main.tf`에서 AWS 리소스 정의를 마무리
  - S3 파이프라인 버킷
    - 버킷명: `lovv-data-pipeline-${env}-${account_id}`
    - 현재 기본값: `lovv-data-pipeline-dev-925273580929`
    - 버킷 정책: 퍼블릭 차단, 버저닝, SSE(AES256), 수명 주기(30일/60일)
  - DynamoDB
    - 테이블명: `TourKoreaDomainData`
    - PK: `PK`, SK: `SK`, PAY_PER_REQUEST
    - GSI
      - `GSI1(entity_id)`
      - `GSI2(geohash_prefix, SK)`
  - Lambda
    - `kr-transformer`, `kr-loader`
    - 공통 패키지: `src/` 전체 Zip 배포
    - Python 런타임: `python3.12`
  - IAM, CloudWatch Log Group, 권한 정책 적용
- Terraform 상태 충돌/기존 리소스 충돌 이슈 대응
  - Lambda 아카이브 경로 오류: `./../src` -> `./../../src` 수정
  - 기존 함수 충돌(409) 발생 시 `terraform import`로 상태 동기화 후 `plan` 정상화

### 2.2 데이터 파이프라인 코드 정비
- 패키지 구조 정리
  - `src/kr_details_pipeline/`에 Raw-Ingest / Transform / Load 모듈 정비
  - Lambda 핸들러 패스는 `src/kr_details_pipeline/handlers/*_handler.py`
- 주요 엔트리포인트
  - `raw-ingest`: 로컬 JSON을 S3 raw 경로로 업로드
  - `transform`: raw JSON을 상태 기반 payload로 분기
  - `load`: 처리 결과를 `TourKoreaDomainData` 엔트리에 적재할 형태로 정규화
- 결과
 - 원본 수집 파이프라인의 1차 실무 실행 기준이 되는 키 규칙과 쓰기 규칙 정리 완료
 - 변환 규칙은 `city_id`, `PK`, `SK`, `entity_id`, `quality_status`, `SK=STAT#yyyymm` 패턴 적용

### 2.3 실행 보강/안전성
- `.env`를 실환경 코드에서 직접 참조하지 않도록 구조화
- `.gitignore`에 환경 파일·로컬 가상환경·임시 캐시 산출물 반영
- 문서화(README, 보고서용 템플릿형 산출물) 반영

## 3. 이번 요청에 따른 산출 문서
- 작업 결과 정리 문서: `docs/reports/work_progress_report.md`(본 문서)
- 쿼리 사용 가이드: `docs/reports/query_usage_guide.md`(새로 작성)

## 4. 현재 상태(요약)
- 상태 관리: 크롤링/적재 기본 흐름은 구성됨
- 남은 리스크
  - `geohash_prefix` 현재 값이 기본 `UNKNOWN`인 항목 존재 가능성
  - 운영환경 정식 자동 오케스트레이션은 다음 단계에서 이벤트 트리거/스케줄러 연동 필요

## 5. 권장 다음 작업
1. `raw` → `transform` → `loader` 순서의 일괄 실행 문서화된 운영 스크립트 추가
2. `geohash_prefix` 정합성 보강 후 `GSI2` 활용 쿼리 고도화
3. Query 동작 검증용 샘플 쿼리(지역별/콘텐츠별/상태별) 자동화 테스트 추가
