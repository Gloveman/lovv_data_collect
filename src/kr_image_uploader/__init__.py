"""S3 image uploader for KR city attraction images.

Reads a raw VisitKorea city JSON (the same files produced by the
``kr_details_pipeline`` raw ingest), extracts ``firstimage`` / ``firstimage2``
URLs, romanizes each attraction title into an ASCII filename, and uploads the
images to ``s3://<bucket>/images/KR/<City>/<Name>_<n>.<ext>``.
"""

from __future__ import annotations

from .extract import ImageTarget, collect_image_targets
from .romanize import romanize
from .s3_keys import build_image_key, safe_name
from .uploader import UploadResult, upload_city

__all__ = [
    "romanize",
    "collect_image_targets",
    "ImageTarget",
    "build_image_key",
    "safe_name",
    "upload_city",
    "UploadResult",
]
