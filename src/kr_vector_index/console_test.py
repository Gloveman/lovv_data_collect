"""Console-friendly smoke test for the KR S3 Vector index.

This script writes one deterministic test vector and queries it back. It does
not delete vectors. It uses AWS CLI `s3vectors` so it can run in AWS CloudShell
or a local terminal without depending on boto3 service model freshness.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

TEST_VECTOR_KEY = "console-test#smoke#0001"


def build_float32_vector(dimension: int) -> list[float]:
    if dimension < 1:
        raise ValueError("dimension must be >= 1")
    seed_values = [round(1.0 / (2 ** (index + 1)), 8) for index in range(16)]
    return [seed_values[index % len(seed_values)] for index in range(dimension)]


def build_test_vectors(dimension: int = 1024) -> list[dict[str, Any]]:
    return [
        {
            "key": TEST_VECTOR_KEY,
            "data": {"float32": build_float32_vector(dimension)},
            "metadata": {
                "country": "KR",
                "entity_type": "console_test",
                "city_id": "KR-ConsoleTest",
                "theme_tags": ["console_test"],
                "raw_s3_uri": "s3://console-test/not-persisted.json",
                "ddb_pk": "CONSOLE#TEST",
                "ddb_sk": "VECTOR#TEST",
                "embedding_model": "manual-console-test",
            },
        }
    ]


def build_query_vector(dimension: int = 1024) -> dict[str, list[float]]:
    return {"float32": build_float32_vector(dimension)}


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def aws_base_command(args: argparse.Namespace) -> list[str]:
    command = ["aws", "s3vectors"]
    if args.profile:
        command.extend(["--profile", args.profile])
    command.extend(["--region", args.region])
    command.extend(["--cli-read-timeout", "60", "--cli-connect-timeout", "20"])
    return command


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    print(f"$ {' '.join(command)}")
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    return completed


def ensure_success(step: str, completed: subprocess.CompletedProcess[str]) -> None:
    if completed.returncode != 0:
        raise RuntimeError(f"{step} failed with exit code {completed.returncode}")


def run_smoke_test(args: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="lovv-s3vectors-test-") as tmp:
        tmp_dir = Path(tmp)
        vectors_path = tmp_dir / "vectors.json"
        query_vector_path = tmp_dir / "query-vector.json"
        write_json(vectors_path, build_test_vectors(args.dimension))
        write_json(query_vector_path, build_query_vector(args.dimension))

        base = aws_base_command(args)
        target = [
            "--vector-bucket-name",
            args.vector_bucket,
            "--index-name",
            args.index_name,
        ]

        put = run_command(
            [
                *base,
                "put-vectors",
                *target,
                "--vectors",
                f"file://{vectors_path.as_posix()}",
            ]
        )
        ensure_success("put-vectors", put)

        query = run_command(
            [
                *base,
                "query-vectors",
                *target,
                "--top-k",
                "1",
                "--query-vector",
                f"file://{query_vector_path.as_posix()}",
                "--return-distance",
            ]
        )
        ensure_success("query-vectors", query)

        if TEST_VECTOR_KEY not in query.stdout:
            raise RuntimeError(f"query-vectors did not return {TEST_VECTOR_KEY}")

        print(f"Kept test vector: {TEST_VECTOR_KEY}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test the KR S3 Vector index from console.")
    parser.add_argument("--vector-bucket", default="lovv-vector-dev")
    parser.add_argument("--index-name", default="kr-tour-domain-v1")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--dimension", type=int, default=1024)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_smoke_test(args)
    except Exception as exc:  # noqa: BLE001 - console script should print a concise failure.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
