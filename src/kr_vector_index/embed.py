"""Amazon Titan embedding client for KR vector indexing."""

from __future__ import annotations

import json
import time
from typing import Any

EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBEDDING_DIMENSION = 1024


class EmbeddingError(RuntimeError):
    """Raised when embedding generation fails."""


def embed_text(client: Any, text: str, *, model_id: str = EMBED_MODEL_ID, retries: int = 3) -> list[float]:
    payload = {"inputText": text, "dimensions": EMBEDDING_DIMENSION, "normalize": True}
    for attempt in range(retries):
        try:
            response = client.invoke_model(modelId=model_id, body=json.dumps(payload).encode("utf-8"))
            body = response["body"].read()
            parsed = json.loads(body)
            embedding = parsed.get("embedding")
            if not isinstance(embedding, list) or len(embedding) != EMBEDDING_DIMENSION:
                raise EmbeddingError(f"unexpected embedding dimension: {len(embedding) if isinstance(embedding, list) else 'missing'}")
            return [float(value) for value in embedding]
        except Exception as exc:
            if attempt == retries - 1:
                raise EmbeddingError(str(exc)) from exc
            time.sleep(2**attempt)
    raise EmbeddingError("embedding retry loop exhausted")


def embed_chunks(client: Any, chunks: list[Any]) -> list[list[float]]:
    return [embed_text(client, chunk.embedding_text) for chunk in chunks]
