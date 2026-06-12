# S3 Vector Console Smoke Test Usage

Use this script from AWS CloudShell, PowerShell, or any terminal where AWS CLI v2 supports `s3vectors`.

## Purpose

The smoke test writes one deterministic test vector to `lovv-vector-dev/kr-tour-domain-v1` and queries it back.

It does not use real Lovv content data or embeddings.
It keeps the vector by default so it remains visible in the console.

## Run

From the project root:

```powershell
python src\kr_vector_index\console_test.py --profile skn26_final
```

For AWS CloudShell, omit `--profile` if the shell already has the target account credentials:

```bash
python src/kr_vector_index/console_test.py
```

## Expected Output

The query result should include:

```text
key: console-test#smoke#0001
```

The script should finish with:

```text
Kept test vector: console-test#smoke#0001
```

## Cleanup

This script does not delete vectors. Cleanup must be a separate, explicitly reviewed operation.
