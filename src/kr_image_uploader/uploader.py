"""Download city attraction images and upload them to S3."""

from __future__ import annotations

import os
from typing import Any, Protocol
from urllib.error import HTTPError, URLError

from . import download
from .extract import collect_image_targets
from .s3_keys import DEFAULT_PREFIX, build_image_key

_CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "bmp": "image/bmp",
    "gif": "image/gif",
    "webp": "image/webp",
}


class S3Client(Protocol):
    """Minimal subset of the boto3 S3 client used here (eases testing)."""

    def put_object(self, **kwargs: Any) -> Any:
        ...


class UploadResult:
    def __init__(self, city: str, uploaded: int, failed: int) -> None:
        self.city = city
        self.uploaded = uploaded
        self.failed = failed

    def __repr__(self) -> str:
        return f"UploadResult(city={self.city!r}, uploaded={self.uploaded}, failed={self.failed})"


def _ext_from_url(url: str) -> str:
    path = url.split("?")[0]
    return os.path.splitext(path)[1].lstrip(".") or "jpg"


def _content_type(ext: str) -> str:
    return _CONTENT_TYPES.get(ext.lower().lstrip("."), "application/octet-stream")


def upload_city(
    payload: dict[str, Any],
    city: str,
    bucket: str,
    client: S3Client | None,
    prefix: str = DEFAULT_PREFIX,
    dry_run: bool = False,
    timeout: int = 30,
) -> UploadResult:
    """Process one city payload: download each image and put it to S3.

    When ``dry_run`` is True, only the planned keys are printed and ``client``
    may be ``None``.
    """
    targets = collect_image_targets(payload)
    print(f"[{city}] image targets: {len(targets)}")

    uploaded = 0
    failed = 0
    for target in targets:
        ext = _ext_from_url(target.url)
        key = build_image_key(city, target.name, target.suffix, ext, prefix=prefix)

        if dry_run:
            print(f"  {key}  <  {target.url}")
            continue

        if client is None:
            raise ValueError("client is required when dry_run is False")

        try:
            body = download.fetch_bytes(target.url, timeout=timeout)
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=body,
                ContentType=_content_type(ext),
            )
            uploaded += 1
            print(f"  [OK]   {key}")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            failed += 1
            print(f"  [FAIL] {target.url} ({type(exc).__name__}: {exc})")

    if not dry_run:
        print(f"[{city}] done: uploaded {uploaded} / failed {failed}")
    return UploadResult(city, uploaded, failed)
