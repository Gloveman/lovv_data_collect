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
