# -----------------------------------------------------------------------------
# Lambda Layer: requests (HTTP 클라이언트)
# -----------------------------------------------------------------------------
# 외부 CDN에서 이미지를 다운로드하기 위해 requests 라이브러리를 Lambda Layer로 제공합니다.
# 빌드: layers/requests/build.sh 실행 후 layer.zip 생성
# 호환 런타임: Python 3.12 / x86_64

resource "aws_lambda_layer_version" "requests" {
  layer_name          = "lovv-requests-layer-${var.env}"
  description         = "requests library and dependencies for Python 3.12 (urllib3, certifi, charset-normalizer, idna)"
  filename            = "${path.module}/../../layers/requests/layer.zip"
  source_code_hash    = filebase64sha256("${path.module}/../../layers/requests/layer.zip")
  compatible_runtimes = ["python3.12"]

  compatible_architectures = ["x86_64"]
}
