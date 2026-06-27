# KR Data Pipeline - DynamoDB Load 실행 보고서

## 실행 요약

| 항목 | 값 |
|---|---|
| 실행 일시 | 2026-06-27 |
| Lambda 함수 | `kr-pipeline-loader` |
| 명령 | `load` (S3 processed → DynamoDB) |
| S3 소스 버킷 | `lovv-data-pipeline-dev-925273580929` |
| S3 프리픽스 | `processed/KR/details/20260609/passed/` |
| 대상 DynamoDB 테이블 | `TourKoreaDomainDataV2` |
| 상태 코드 | **200 (성공)** |

## 적재 결과

| 메트릭 | 값 |
|---|---|
| S3에서 읽은 총 아이템 | **4,291** |
| DynamoDB 적재 성공 | **4,291** |
| DynamoDB 적재 실패 | **0** |
| 에러 | **0** |

## 배포된 인프라

### Lambda 함수 (kr-pipeline-* prefix)

| Lambda 이름 | 역할 | 런타임 | 타임아웃 |
|---|---|---|---|
| `kr-pipeline-transform` | raw → processed 변환 | Python 3.12 | 300s |
| `kr-pipeline-loader` | DynamoDB 적재 + Vector build | Python 3.12 | 900s |
| `kr-pipeline-vector` | Vector 빌드 standalone | Python 3.12 | 900s |
| `kr-pipeline-image` | 이미지 다운로드 + S3 적재 | Python 3.12 | 900s |

### Step Functions

| 리소스 | 값 |
|---|---|
| 상태 머신 이름 | `kr-data-pipeline-dev` |
| 흐름 | Transform → Image(Map/10) → Load → Vector → Report |

### 스토리지

| 리소스 | 상태 | 용도 |
|---|---|---|
| `TourKoreaDomainDataV2` | ACTIVE, 4,291 items | 도메인 데이터 |
| `lovv-pipeline-images-dev-925273580929` | ACTIVE, 비어있음 | 이미지 전용 |
| `lovv-data-pipeline-dev-925273580929` | ACTIVE | 파이프라인 데이터 |
| `lovv-vector-dev` / `kr-tour-domain-v1` | ACTIVE | 벡터 인덱스 |

## 소스 데이터 (20260609)

- **도시 수**: 40개 (경북/강원 지역)
- **총 레코드**: 4,291개
- **entity types**: city, attraction, festival, visitor_statistics
- **이미지 URL 보유 레코드**: ~3,811개 (89%)
