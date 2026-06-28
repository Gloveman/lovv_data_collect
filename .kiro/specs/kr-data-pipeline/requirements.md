# Requirements Document

## Introduction

전국 211개 도시(17개 광역시/도)의 관광 데이터를 S3에서 읽어 이미지를 자체 S3에 적재하고, DynamoDB에 데이터를 로드한 뒤 벡터 인덱스를 빌드하는 End-to-End 자동 파이프라인을 구현한다. AWS Step Functions로 전체 흐름을 오케스트레이션하며, 도시 단위 병렬 처리로 Lambda 15분 타임아웃 제약을 해결한다.

**기존 Lambda 활용 전략 (이름 변경 포함):**
- `kr-pipeline-transform` → `kr-pipeline-transform`: raw → processed 변환에 그대로 사용
- `kr-pipeline-loader` → `kr-pipeline-loader`: `load` 명령으로 S3 processed → DynamoDB 적재, `vector-build` 명령으로 벡터 빌드에 그대로 사용
- `kr-pipeline-vector` → `kr-pipeline-vector`: 벡터 빌드 전용 Lambda로 그대로 사용 가능 (backup)
- `kr-raw-ingest` → `kr-pipeline-ingest`: raw S3 업로드 (기존 기능 그대로)
- **신규 Lambda 1개만 추가**: `kr-pipeline-image` — 도시 단위 이미지 다운로드+S3 적재 전담

핵심 흐름:
1. `kr-pipeline-transform` (기존 `kr-pipeline-transform`) 로 raw → processed 변환 (기존 기능 그대로)
2. `kr-pipeline-image` (신규) 로 이미지 다운로드 → S3 적재 → image_url을 S3 URL로 변환
3. `kr-pipeline-loader` (기존 `kr-pipeline-loader`, `load` 명령) 으로 DynamoDB 적재
4. `kr-pipeline-loader` (기존 `kr-pipeline-loader`, `vector-build` 명령) 으로 벡터 인덱스 재빌드

## Glossary

- **E2E_Pipeline**: S3 데이터 로드부터 벡터 빌드까지 전체 흐름을 자동 실행하는 파이프라인
- **State_Machine**: AWS Step Functions 상태 머신. 파이프라인 단계별 실행을 오케스트레이션
- **Map_State**: Step Functions Map State. 도시 목록을 입력으로 받아 병렬로 Lambda를 호출
- **Image_Stage**: 외부 CDN에서 이미지를 다운로드하여 이미지 전용 S3 버킷에 적재하는 단계
- **Image_Bucket**: 파이프라인 전용 이미지 S3 버킷 (`lovv-pipeline-images-{env}-{account_id}`). 기존 앱 이미지 버킷과 완전히 분리된 새 버킷
- **S3_Image_URL**: 파이프라인 이미지 버킷에 적재된 이미지의 URL (형식: `https://{Image_Bucket}.s3.amazonaws.com/images/KR/{city}/{filename}`)
- **Review_Manifest**: 이미지가 없거나 다운로드 실패한 레코드를 모아놓은 JSON 파일
- **Load_Stage**: image_url이 S3 URL로 변환된 레코드를 DynamoDB에 적재하는 단계
- **Vector_Stage**: DynamoDB에서 데이터를 export하여 임베딩 후 S3 Vectors에 업서트하는 단계
- **Transform_Stage**: raw JSON을 processed 형태로 변환하는 단계 (기존 `kr-pipeline-transform` 활용)
- **City_Batch**: Map State에서 처리하는 단일 도시의 데이터 묶음

## Requirements

### Requirement 1: Step Functions 상태 머신 오케스트레이션

**User Story:** As a data engineer, I want the entire E2E pipeline to be orchestrated by Step Functions, so that each stage executes automatically in sequence with error handling and retry logic.

#### Acceptance Criteria

1. THE State_Machine SHALL define the following sequential stages: Transform_Stage (선택) → Image_Stage → Load_Stage → Vector_Stage
2. WHEN the State_Machine is started with an execution input containing `bucket`, `ingest_date`, `table_name`, THE State_Machine SHALL pass these parameters to each stage
3. IF any stage fails with a non-recoverable error, THEN THE State_Machine SHALL skip subsequent stages and transition to a Failure state with error details
4. WHEN all stages complete successfully, THE State_Machine SHALL transition to a Success state with a combined execution summary
5. THE State_Machine SHALL be defined as Terraform resource in `infrastructure/terraform/`
6. THE State_Machine SHALL accept optional `province_id` parameter to scope execution to a single province for testing
7. THE State_Machine SHALL invoke existing Lambda functions by ARN (no code duplication)

### Requirement 2: 도시 단위 병렬 이미지 처리 (신규 Lambda: kr-pipeline-image)

**User Story:** As a data engineer, I want image downloads to be parallelized across cities using Step Functions Map State and a dedicated image processing Lambda, so that 211 cities can be processed within reasonable time.

#### Acceptance Criteria

1. THE Image_Stage SHALL use a Map State to invoke `kr-pipeline-image` Lambda per city with `MaxConcurrency` of 10
2. THE `kr-pipeline-image` Lambda SHALL be the only new Lambda function added to the project
3. WHEN invoked with a city batch, THE `kr-pipeline-image` SHALL download all image_url(s) from the city's records and upload them to the Image_Bucket at `images/KR/{city_name_en}/{filename}`
4. WHEN an image download succeeds, THE `kr-pipeline-image` SHALL return the record with `image_url` replaced by the S3 URL of the Image_Bucket
5. WHEN an image download fails (404, timeout, network error), THE `kr-pipeline-image` SHALL mark the record for review and continue processing remaining images
6. THE `kr-pipeline-image` Lambda SHALL reuse `kr_image_uploader` module logic (download.fetch_bytes, s3_keys.build_image_key, romanize)
7. EACH city batch Lambda invocation SHALL complete within 15 minutes (Lambda timeout)
8. THE `kr-pipeline-image` Lambda SHALL output image-processed records to S3 at `processed/KR/details/{ingest_date}/images/{city_name_en}.json`

### Requirement 3: 이미지 없는 레코드 Review 분리

**User Story:** As a data engineer, I want records without images to be separated into a review manifest, so that I can identify and manually fix records missing visual content.

#### Acceptance Criteria

1. WHEN a record's original image_url is null or empty, THE `kr-pipeline-image` SHALL add the record to the review manifest with reason "no_source_image"
2. WHEN an image download fails after 3 retry attempts, THE `kr-pipeline-image` SHALL add the record to the review manifest with reason "download_failed" and include the original URL and error message
3. THE review manifest SHALL be written to S3 at `processed/KR/review/{ingest_date}/image_review.json` after all cities complete
4. EACH review manifest entry SHALL include: city_name_en, content_id, entity_type, original_image_url, failure_reason, timestamp
5. THE Load_Stage SHALL still load review records to DynamoDB with `image_status: "needs_review"` field set

### Requirement 4: DynamoDB 적재 (기존 kr-pipeline-loader 활용)

**User Story:** As a data engineer, I want DynamoDB loading to use the existing kr-pipeline-loader Lambda's `load` command, so that no new loading logic needs to be written.

#### Acceptance Criteria

1. THE Load_Stage SHALL invoke the existing `kr-pipeline-loader` Lambda with `{"command": "load"}` and the S3 path to image-processed data
2. THE Load_Stage input SHALL point to `processed/KR/details/{ingest_date}/images/` prefix (Image_Stage output)
3. WHEN a record has a successfully converted S3 image URL, THE Load_Stage SHALL write it to DynamoDB with the S3 URL in the `image_url` field
4. WHEN a record has `image_status: "needs_review"`, THE Load_Stage SHALL write it to DynamoDB preserving that status
5. THE Load_Stage SHALL write to the `TourKoreaDomainDataV2` table (reusing existing `_write_item` logic)
6. THE `kr-pipeline-loader` Lambda's `load` command SHALL be updated to accept an alternative S3 prefix (images/ instead of passed/)

### Requirement 5: 벡터 인덱스 재빌드 (기존 Lambda 활용)

**User Story:** As a data engineer, I want the vector index rebuild to use the existing kr-pipeline-loader Lambda's `vector-build` command, so that no new vectorization logic needs to be written.

#### Acceptance Criteria

1. THE Vector_Stage SHALL invoke the existing `kr-pipeline-loader` Lambda with `{"command": "vector-build", "table_name": "TourKoreaDomainDataV2", "rebuild_mode": "full"}`
2. THE Vector_Stage SHALL execute only after Load_Stage completes successfully
3. THE Vector_Stage SHALL reuse the existing VectorRebuilder logic (EntityTypeDomainIndex GSI, Titan Embed v2, S3 Vectors upsert)
4. IF the Vector_Stage fails, THE State_Machine SHALL record the error but DynamoDB data remains intact (no rollback)
5. THE Vector_Stage output SHALL include a rebuild manifest (items processed, upserted, skipped, errors)

### Requirement 6: Lambda Layer (requests)

**User Story:** As a data engineer, I want a requests library Lambda Layer available, so that the image processor Lambda can make HTTP calls to external CDN URLs.

#### Acceptance Criteria

1. THE Lambda Layer SHALL include `requests` and its dependencies (`urllib3`, `certifi`, `charset-normalizer`, `idna`)
2. THE Lambda Layer SHALL be compatible with Python 3.12 runtime on x86_64 architecture
3. THE Lambda Layer SHALL be attached to `kr-pipeline-image` Lambda
4. THE Lambda Layer SHALL also be attached to `kr-pipeline-loader` Lambda (for Wikipedia API in preprocess mode)
5. THE Lambda Layer SHALL be defined as Terraform resource with version tracking
6. THE Lambda Layer unzipped size SHALL not exceed 50MB

### Requirement 7: 전처리 데이터 변환 (기존 kr-pipeline-transform 활용)

**User Story:** As a data engineer, I want the 20260625 raw data (211 cities) to be transformed into processed format using the existing kr-pipeline-transform Lambda, so that it can be used as input to the E2E pipeline.

#### Acceptance Criteria

1. THE Transform_Stage SHALL invoke the existing `kr-pipeline-transform` Lambda per city file in `raw/KR/details/20260625/`
2. THE Transform_Stage SHALL use a Map State to process cities in parallel with `MaxConcurrency` of 10
3. THE `kr-pipeline-transform` Lambda SHALL produce output at `processed/KR/details/20260625/passed/{city_name_en}.json` (기존 동작 그대로)
4. THE Transform_Stage SHALL be the first stage in the State_Machine (optional — skip if processed data already exists)
5. WHEN the State_Machine input includes `skip_transform: true`, THE Transform_Stage SHALL be bypassed

### Requirement 8: 실행 보고서 및 모니터링

**User Story:** As a data engineer, I want a comprehensive execution report after each pipeline run, so that I can monitor data quality and troubleshoot failures.

#### Acceptance Criteria

1. WHEN the State_Machine completes (success or failure), THE final stage SHALL write an execution report to S3 at `processed/KR/reports/{ingest_date}/pipeline_report.json`
2. THE execution report SHALL include: total cities processed, images downloaded, images failed, review count, records loaded to DynamoDB, vectors built, total execution time
3. THE execution report SHALL include per-city breakdown (images_ok, images_failed, records_loaded)
4. WHEN the State_Machine fails, THE report SHALL include the failed stage name, error message, and items processed before failure
5. THE State_Machine execution history SHALL be viewable in AWS Step Functions console with per-stage timing

### Requirement 9: IAM 및 인프라 정리

**User Story:** As a data engineer, I want all IAM permissions properly configured for the new Lambda and Step Functions, and the DynamoDB V2 table cleaned before full pipeline execution, so that the pipeline runs without permission errors and starts from a clean state.

#### Acceptance Criteria

1. THE Terraform configuration SHALL create a new S3 bucket `lovv-pipeline-images-{env}-{account_id}` dedicated to pipeline image storage, separate from existing app buckets
2. THE new Image_Bucket SHALL have versioning disabled, SSE-S3 encryption enabled, and public access blocked
3. THE `kr-pipeline-image` Lambda role SHALL have S3 read/write access to the Image_Bucket and S3 read access to the pipeline data bucket
4. THE Step Functions execution role SHALL have permission to invoke all 4 Lambda functions (`kr-pipeline-transform`, `kr-pipeline-image`, `kr-pipeline-loader`, `kr-pipeline-vector`)
5. THE Step Functions execution role SHALL have CloudWatch Logs permission for execution logging
6. THE existing `kr-pipeline-loader` Lambda role SHALL retain its current permissions (DynamoDB, S3, Bedrock, S3 Vectors)
7. ALL new Terraform resources SHALL be added without modifying or deleting existing Lambda functions or buckets
8. BEFORE the first full pipeline execution, THE `TourKoreaDomainDataV2` table SHALL be deleted and recreated (empty state) to remove stale partial data from previous test runs
9. THE table deletion and recreation SHALL be handled via Terraform (state rm + apply) or a dedicated cleanup script


### Requirement 10: Lambda 이름 변경 (kr-pipeline-* prefix 통일)

**User Story:** As a data engineer, I want all pipeline Lambda functions to have consistent, descriptive names with a `kr-pipeline-*` prefix, so that the infrastructure is self-documenting and easy to navigate in the AWS console.

#### Acceptance Criteria

1. THE existing `kr-domain-loader` Lambda SHALL be renamed to `kr-pipeline-transform`
2. THE existing `kr-unified-pipeline` Lambda SHALL be renamed to `kr-pipeline-loader`
3. THE existing `kr-vector-index` Lambda SHALL be renamed to `kr-pipeline-vector`
4. THE existing `kr-raw-ingest` Lambda SHALL be renamed to `kr-pipeline-ingest`
5. THE new image processing Lambda SHALL be named `kr-pipeline-image`
6. THE Lambda handler code paths SHALL remain unchanged (only function_name changes in Terraform)
7. THE Terraform `locals.lambda_names` map SHALL be updated to reflect all new names
8. THE rename SHALL be executed as Terraform destroy+create (Lambda does not support in-place rename)
9. ALL CloudWatch Log Groups SHALL be updated to match new Lambda names (`/aws/lambda/kr-pipeline-*`)
