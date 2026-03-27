"""Embedding Tools - Tools for generating and searching text embeddings.

Registers the following as tools Jo can use:
- embed_text: Generate embedding vector for given text
- vault_semantic_search: Search vault notes by semantic similarity using embeddings
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# Optional imports
try:
    from sentence_transformers import SentenceTransformer

    _model = SentenceTransformer("all-MiniLM-L6-v2")
    _model_available = True
except Exception:  # ImportError or runtime error
    _model = None
    _model_available = False
    log.warning("sentence-transformers not available; embedding tools will be disabled")

try:
    import numpy as np

    _numpy_available = True
except Exception:
    _numpy_available = False
    log.warning("numpy not available; embedding similarity will use slower pure Python")


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    if _numpy_available:
        import numpy as np

        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    else:
        # Manual computation
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


def _embed_text(
    ctx: ToolContext,
    text: str,
) -> str:
    """Generate embedding vector for given text.

    Args:
        text: Input text to embed

    Returns:
        JSON string with embedding vector or error message
    """
    if not _model_available:
        return json.dumps({"error": "Embedding model not available. Install sentence-transformers.", "embedding": None})

    if not text or not text.strip():
        return json.dumps({"error": "Empty text provided", "embedding": None})

    try:
        embedding = _model.encode(text.strip())
        # Convert to list of floats for JSON serialization
        embedding_list = [float(x) for x in embedding]
        return json.dumps(
            {
                "text": text[:100] + ("..." if len(text) > 100 else ""),
                "embedding": embedding_list,
                "dimension": len(embedding_list),
            }
        )
    except Exception as e:
        log.error(f"Embedding generation failed: {e}")
        return json.dumps({"error": f"Embedding generation failed: {str(e)}", "embedding": None})


def _vault_semantic_search(
    ctx: ToolContext,
    query: str,
    top_k: int = 5,
) -> str:
    """Search vault notes by semantic similarity using embeddings.

    Args:
        query: Search query text
        top_k: Number of results to return (default 5)

    Returns:
        JSON string with search results
    """
    if not _model_available:
        return json.dumps({"error": "Embedding model not available. Install sentence-transformers.", "results": []})

    if not query or not query.strip():
        return json.dumps({"error": "Empty query provided", "results": []})

    try:
        # Embed the query
        query_embedding = _model.encode(query.strip())
        query_list = [float(x) for x in query_embedding]
    except Exception as e:
        return json.dumps({"error": f"Failed to embed query: {str(e)}", "results": []})

    # Determine vault directory
    vault_dir = ctx.drive_path("vault")
    if not vault_dir.exists():
        return json.dumps({"error": "Vault directory not found", "results": []})

    # Collect all markdown notes
    results: List[Dict[str, Any]] = []
    for note_path in vault_dir.rglob("*.md"):
        try:
            # Try to load existing embedding sidecar
            embedding_path = note_path.with_suffix(".md.embedding.json")
            if embedding_path.exists():
                with open(embedding_path, "r", encoding="utf-8") as f:
                    embedding_data = json.load(f)
                stored_embedding = embedding_data.get("embedding")
                note_text = embedding_data.get("text", "")
            else:
                # Fallback: read note and compute embedding on the fly (slower)
                note_text = note_path.read_text(encoding="utf-8")
                # Truncate very long notes to avoid excessive computation
                if len(note_text) > 5000:
                    note_text = note_text[:5000] + "..."
                embedding = _model.encode(note_text)
                stored_embedding = [float(x) for x in embedding]
                # Optionally save the embedding for next time
                try:
                    with open(embedding_path, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "text": note_text[:200] + ("..." if len(note_text) > 200 else ""),
                                "embedding": stored_embedding,
                            },
                            f,
                        )
                except Exception:
                    pass  # Ignore errors saving embedding

            if not stored_embedding:
                continue

            similarity = _cosine_similarity(query_list, stored_embedding)
            results.append(
                {
                    "note": str(note_path.relative_to(vault_dir)),
                    "similarity": float(similarity),
                    "text_preview": note_text[:200] + ("..." if len(note_text) > 200 else ""),
                    "path": str(note_path),
                }
            )
        except Exception as e:
            log.debug(f"Failed to process note {note_path}: {e}")
            continue

    # Sort by similarity descending
    results.sort(key=lambda x: x["similarity"], reverse=True)
    top_results = results[:top_k]

    return json.dumps(
        {
            "query": query[:100] + ("..." if len(query) > 100 else ""),
            "results_count": len(top_results),
            "results": top_results,
        }
    )
