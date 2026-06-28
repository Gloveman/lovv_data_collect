# S3 Vectors - kr-tour-domain-v1 사용 가이드

## 벡터 인덱스 개요

| 항목 | 값 |
|---|---|
| S3 Vectors 버킷 | `lovv-vector-dev` |
| 인덱스 이름 | `kr-tour-domain-v1` |
| 임베딩 모델 | Amazon Titan Embed Text v2 |
| 벡터 차원 | 1024 |
| 소스 테이블 | `TourKoreaDomainDataV2` (EntityTypeDomainIndex GSI) |

## 벡터 빌드 실행

### Lambda를 통한 빌드

```bash
# payload 생성
echo '{"command":"vector-build","table_name":"TourKoreaDomainDataV2","rebuild_mode":"full"}' > payload.json

# Lambda invoke
aws lambda invoke \
  --function-name kr-pipeline-loader \
  --cli-read-timeout 900 \
  --payload fileb://payload.json \
  response.json
```

### CLI를 통한 빌드 (로컬)

```bash
cd src
python -m kr_vector_index.cli \
  --table-name TourKoreaDomainDataV2 \
  --vector-bucket lovv-vector-dev \
  --index-name kr-tour-domain-v1 \
  build
```

### 벡터 빌드 흐름

```
DynamoDB (EntityTypeDomainIndex GSI)
  → export_items() : entity_type별 vectorizable 아이템 추출
  → build_chunks() : 텍스트 청크 + 메타데이터 생성
  → embed_chunks() : Bedrock Titan Embed v2로 임베딩
  → put_vectors_sdk() : S3 Vectors에 업서트
```

## 벡터 검색 (Query)

### Python (boto3 s3vectors)

```python
import boto3
import json

# Bedrock로 쿼리 텍스트 임베딩
bedrock = boto3.client('bedrock-runtime')
query_text = "강릉에서 바다를 볼 수 있는 관광지"

embed_response = bedrock.invoke_model(
    modelId='amazon.titan-embed-text-v2:0',
    body=json.dumps({
        "inputText": query_text,
        "dimensions": 1024,
        "normalize": True,
    })
)
query_vector = json.loads(embed_response['body'].read())['embedding']

# S3 Vectors 검색
s3vectors = boto3.client('s3vectors')
search_response = s3vectors.query_vectors(
    vectorBucketName='lovv-vector-dev',
    indexName='kr-tour-domain-v1',
    queryVector=query_vector,
    topK=10,
)

# 결과 처리
for result in search_response['vectors']:
    metadata = result.get('metadata', {})
    print(f"Score: {result['distance']:.4f}")
    print(f"  Title: {metadata.get('title')}")
    print(f"  City: {metadata.get('city_name_ko')}")
    print(f"  Type: {metadata.get('entity_type')}")
    print(f"  Tags: {metadata.get('theme_tags')}")
    print()
```

### 검색 결과 메타데이터 필드

벡터에 저장되는 메타데이터:

| 필드 | 타입 | 설명 |
|---|---|---|
| country | string | 국가 코드 (KR) |
| province | string | 광역시/도 |
| city_id | string | 도시 ID |
| city_name_en | string | 영문 도시명 |
| city_name_ko | string | 한글 도시명 |
| entity_type | string | city/attraction/festival |
| source_type | string | 데이터 소스 타입 |
| source_id | string | 소스 ID |
| place_id | string | 장소 ID |
| title | string | 제목 |
| class_tags | list | 분류 태그 |
| theme_tags | list | 테마 태그 |
| season_tags | list | 계절 태그 |
| visit_months | list | 방문 추천 월 |
| latitude | float | 위도 |
| longitude | float | 경도 |

## 검색 시나리오 예시

### 1. 테마 기반 검색

```python
query = "겨울에 눈꽃을 볼 수 있는 축제"
# → 평창 눈꽃축제, 태백산 눈축제 등 반환
```

### 2. 지역 + 활동 검색

```python
query = "강원도에서 서핑할 수 있는 해변"
# → 양양 서피비치, 속초 해변 등 반환
```

### 3. 음식/문화 검색

```python
query = "전통 한옥마을을 체험할 수 있는 곳"
# → 안동 하회마을, 경주 교촌마을 등 반환
```

## IAM 권한

### 벡터 검색 (읽기 전용)

```json
{
  "Effect": "Allow",
  "Action": [
    "s3vectors:GetVectorBucket",
    "s3vectors:GetIndex",
    "s3vectors:QueryVectors"
  ],
  "Resource": [
    "arn:aws:s3vectors:{region}:{account}:bucket/lovv-vector-dev",
    "arn:aws:s3vectors:{region}:{account}:bucket/lovv-vector-dev/index/kr-tour-domain-v1"
  ]
}
```

### 벡터 빌드 (쓰기)

```json
{
  "Effect": "Allow",
  "Action": [
    "s3vectors:GetVectorBucket",
    "s3vectors:GetIndex",
    "s3vectors:ListVectors",
    "s3vectors:GetVectors",
    "s3vectors:QueryVectors",
    "s3vectors:PutVectors"
  ],
  "Resource": [
    "arn:aws:s3vectors:{region}:{account}:bucket/lovv-vector-dev",
    "arn:aws:s3vectors:{region}:{account}:bucket/lovv-vector-dev/index/kr-tour-domain-v1"
  ]
}
```

## 주의사항

1. **벡터 빌드 비용**: Bedrock Titan Embed v2 호출 비용 발생 (아이템당 ~$0.00003)
2. **빌드 시간**: 4,291개 아이템 기준 약 5~8분 소요 (Lambda 15분 타임아웃 내)
3. **증분 빌드**: `rebuild_mode: "incremental"` 옵션으로 변경된 아이템만 재빌드 가능
4. **GSI 의존성**: `EntityTypeDomainIndex` GSI를 통해 데이터를 export하므로 해당 GSI가 활성 상태여야 함
