output "bucket_name" {
  # Phase 0/운영에서 생성된 파이프라인 S3 버킷 식별자
  description = "Pipeline artifact bucket name."
  value       = aws_s3_bucket.pipeline.bucket
}

output "bucket_arn" {
  # 버킷 ARN (IAM 정책 연동 또는 외부 참조에 사용).
  description = "Pipeline artifact bucket ARN."
  value       = aws_s3_bucket.pipeline.arn
}

output "domain_dynamodb_table_name" {
  # 음식점/관광지/축제 분리 전처리 결과를 적재할 신규 테이블 이름.
  description = "Domain-separated KR content table."
  value       = aws_dynamodb_table.tourkorea_domain_data.name
}

output "domain_dynamodb_table_arn" {
  # 신규 도메인 분리 테이블 ARN.
  description = "Domain-separated KR content table ARN."
  value       = aws_dynamodb_table.tourkorea_domain_data.arn
}

output "lambda_role_arn" {
  # 다음 단계 Lambda 생성 시 재사용할 IAM 역할 ARN.
  description = "IAM role for pipeline lambdas."
  value       = aws_iam_role.pipeline_lambda_role.arn
}

output "kr_domain_loader_lambda_name" {
  # Raw JSON을 도메인별로 전처리한 뒤 신규 DynamoDB 테이블에 적재하는 수동 실행용 Lambda.
  description = "Name of deployed KR domain loader Lambda function."
  value       = aws_lambda_function.kr_domain_loader.function_name
}

output "kr_domain_loader_lambda_arn" {
  # kr-domain-loader Lambda ARN.
  description = "ARN of deployed KR domain loader Lambda function."
  value       = aws_lambda_function.kr_domain_loader.arn
}

output "kr_vector_index_lambda_name" {
  # S3 Vector index build Lambda function name.
  description = "Name of deployed KR vector index Lambda function."
  value       = aws_lambda_function.kr_vector_index.function_name
}

output "kr_vector_index_lambda_arn" {
  # kr-vector-index Lambda ARN.
  description = "ARN of deployed KR vector index Lambda function."
  value       = aws_lambda_function.kr_vector_index.arn
}

output "vector_bucket_name" {
  # S3 Vector bucket name used by the KR vector index.
  description = "S3 Vector bucket name for KR vector indexes."
  value       = var.vector_bucket_name
}

output "kr_vector_index_name" {
  # S3 Vector index name used for KR tourism domain search.
  description = "S3 Vector index name for KR tourism domain data."
  value       = var.kr_vector_index_name
}

output "kr_vector_index_arn" {
  # S3 Vector index ARN for writer/reader policy references.
  description = "ARN of the KR S3 Vector index."
  value       = local.kr_vector_index_arn
}

output "s3_vector_index_writer_role_arn" {
  # Role for index build/upsert jobs.
  description = "IAM role ARN for S3 Vector index writer jobs."
  value       = aws_iam_role.s3_vector_index_writer_role.arn
}

output "s3_vector_index_reader_role_arn" {
  # Role for Candidate Evidence Agent retrieval queries.
  description = "IAM role ARN for S3 Vector index reader queries."
  value       = aws_iam_role.s3_vector_index_reader_role.arn
}
