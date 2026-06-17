"""Command-line entry point for the KR image uploader.

Examples
--------
  # one city
  python -m kr_image_uploader.cli --json Cheorwon.json --city Cheorwon

  # every {City}.json in a folder (city name taken from the file name)
  python -m kr_image_uploader.cli --dir rawjson

  # preview only (no download / no upload, no AWS needed)
  python -m kr_image_uploader.cli --dir rawjson --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from .s3_keys import DEFAULT_PREFIX
from .uploader import upload_city

DEFAULT_BUCKET = "lovv-image-dev-925273580929"


def _load_payload(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _make_s3_client() -> Any:
    import boto3

    return boto3.client("s3")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload KR city attraction images to S3.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", help="single raw city JSON file")
    source.add_argument("--dir", help="folder containing {City}.json files")
    parser.add_argument("--city", help="city name (S3 folder); defaults to the JSON file name")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--dry-run", action="store_true", help="list planned keys only")
    args = parser.parse_args(argv)

    client = None if args.dry_run else _make_s3_client()

    if args.json:
        city = args.city or os.path.splitext(os.path.basename(args.json))[0]
        upload_city(_load_payload(args.json), city, args.bucket, client,
                    prefix=args.prefix, dry_run=args.dry_run)
    else:
        files = sorted(f for f in os.listdir(args.dir) if f.lower().endswith(".json"))
        print(f"Found {len(files)} city JSON files in {args.dir}\n")
        for name in files:
            city = os.path.splitext(name)[0]
            print(f"===== {city} =====")
            upload_city(_load_payload(os.path.join(args.dir, name)), city, args.bucket,
                        client, prefix=args.prefix, dry_run=args.dry_run)
            print()
        print("All cities processed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
