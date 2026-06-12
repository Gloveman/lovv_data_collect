"""CLI for KR S3 Vector index build steps."""

from __future__ import annotations

import argparse
from pathlib import Path

import boto3

from kr_vector_index.chunks import build_chunks
from kr_vector_index.embed import embed_chunks
from kr_vector_index.export import count_by_entity_type, export_items
from kr_vector_index.manifest import build_manifest, write_json
from kr_vector_index.upsert import build_vector_records, put_vectors_cli


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or inspect the KR S3 Vector index.")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--table-name", default="TourKoreaDomainData")
    parser.add_argument("--vector-bucket", default="lovv-vector-dev")
    parser.add_argument("--index-name", default="kr-tour-domain-v1")
    parser.add_argument("--city-pk", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("export-counts")
    build = subparsers.add_parser("build")
    build.add_argument("--manifest-path", default="data/KR/s3-vector/manifests/latest.json")
    build.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def session(args: argparse.Namespace) -> boto3.Session:
    return boto3.Session(profile_name=args.profile, region_name=args.region) if args.profile else boto3.Session(region_name=args.region)


def main() -> int:
    args = parse_args()
    aws = session(args)
    ddb = aws.client("dynamodb")
    items = export_items(ddb, table_name=args.table_name, city_pk=args.city_pk)
    counts = count_by_entity_type(items)

    if args.command == "export-counts":
        print(counts)
        return 0

    chunks = build_chunks(items)
    if args.dry_run:
        manifest = build_manifest(
            index_name=args.index_name,
            entity_counts=counts,
            chunk_count=len(chunks),
            vector_success_count=0,
        )
        write_json(Path(args.manifest_path), manifest)
        print(f"dry-run chunks={len(chunks)} manifest={args.manifest_path}")
        return 0

    bedrock = aws.client("bedrock-runtime")
    embeddings = embed_chunks(bedrock, chunks)
    records = build_vector_records(chunks, embeddings)
    written = put_vectors_cli(
        records,
        vector_bucket=args.vector_bucket,
        index_name=args.index_name,
        region=args.region,
        profile=args.profile,
    )
    manifest = build_manifest(
        index_name=args.index_name,
        entity_counts=counts,
        chunk_count=len(chunks),
        vector_success_count=written,
    )
    write_json(Path(args.manifest_path), manifest)
    print(f"written={written} manifest={args.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
