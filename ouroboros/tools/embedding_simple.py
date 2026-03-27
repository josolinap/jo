"""Simple embedding tools for Jo using pure-Python TF-IDF and cosine similarity.

No external dependencies required. Provides basic text vectorization and semantic search.
"""

from __future__ import annotations

import json
import logging
import math
import os
import pathlib
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.tools.registry import ToolContext

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tokenizer and text processing
# ---------------------------------------------------------------------------


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase words, removing punctuation."""
    # Simple regex: split on non-alphanumeric, keep sequences of letters/digits
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    # Remove very short tokens (1-2 chars) and stopwords (optional)
    stopwords = {"the", "and", "to", "of", "a", "in", "is", "it", "for", "on", "with", "as", "at", "by"}
    tokens = [t for t in tokens if len(t) > 2 and t not in stopwords]
    return tokens


def compute_tf(tokens: List[str]) -> Dict[str, float]:
    """Compute term frequency for a list of tokens."""
    counts = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {word: count / total for word, count in counts.items()}


def compute_idf(documents: List[List[str]]) -> Dict[str, float]:
    """Compute inverse document frequency across all documents."""
    n_docs = len(documents)
    doc_freq = defaultdict(int)
    for doc_tokens in documents:
        unique_tokens = set(doc_tokens)
        for token in unique_tokens:
            doc_freq[token] += 1
    # Smooth IDF: log((N + 1) / (df + 1)) + 1 to avoid zero
    return {word: math.log((n_docs + 1) / (df + 1)) + 1 for word, df in doc_freq.items()}


def compute_tfidf(tf: Dict[str, float], idf: Dict[str, float]) -> Dict[str, float]:
    """Compute TF-IDF vector for a document given its TF and corpus IDF."""
    return {word: tf_val * idf.get(word, 0) for word, tf_val in tf.items()}


# ---------------------------------------------------------------------------
# Vector operations
# ---------------------------------------------------------------------------


def cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors."""
    # Find common words
    common = set(vec1.keys()) & set(vec2.keys())
    if not common:
        return 0.0
    dot = sum(vec1[w] * vec2[w] for w in common)
    norm1 = math.sqrt(sum(v * v for v in vec1.values())) if vec1 else 0
    norm2 = math.sqrt(sum(v * v for v in vec2.values())) if vec2 else 0
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def vector_from_tokens(tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
    """Create a TF-IDF vector from a list of tokens."""
    tf = compute_tf(tokens)
    return compute_tfidf(tf, idf)


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------


class SimpleIndex:
    """A simple TF-IDF index stored in a JSON file."""

    def __init__(self, index_path: pathlib.Path):
        self.index_path = index_path
        self.documents: Dict[str, Dict[str, Any]] = {}  # key: file path, value: metadata + vector
        self.idf: Dict[str, float] = {}
        self.vocabulary: List[str] = []
        self.loaded = False

    def load(self) -> None:
        """Load index from disk."""
        if self.index_path.exists():
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.documents = data.get("documents", {})
                self.idf = data.get("idf", {})
                self.vocabulary = data.get("vocabulary", [])
                self.loaded = True
                log.debug("Loaded index with %d documents", len(self.documents))
            except Exception as e:
                log.warning("Failed to load index: %s", e)
                self.documents = {}
                self.idf = {}
                self.vocabulary = []
                self.loaded = False

    def save(self) -> None:
        """Save index to disk."""
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "documents": self.documents,
                "idf": self.idf,
                "vocabulary": self.vocabulary,
            }
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.warning("Failed to save index: %s", e)

    def build_from_vault(self, vault_dir: pathlib.Path) -> None:
        """Build index from vault notes."""
        log.info("Building simple index from vault: %s", vault_dir)
        # Collect all markdown files
        note_paths = list(vault_dir.rglob("*.md"))
        if not note_paths:
            log.info("No vault notes found")
            return

        # Read and tokenize each note
        all_tokens = []
        notes_content = {}
        for path in note_paths:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                tokens = tokenize(content)
                all_tokens.append(tokens)
                notes_content[str(path)] = {"content": content, "tokens": tokens}
            except Exception as e:
                log.debug("Failed to read %s: %s", path, e)
                continue

        # Compute IDF across all notes
        self.idf = compute_idf(all_tokens)
        self.vocabulary = list(self.idf.keys())

        # Compute TF-IDF vector for each note
        self.documents = {}
        for path_str, data in notes_content.items():
            vector = vector_from_tokens(data["tokens"], self.idf)
            self.documents[path_str] = {
                "path": path_str,
                "preview": data["content"][:200] + ("..." if len(data["content"]) > 200 else ""),
                "vector": vector,
                "token_count": len(data["tokens"]),
            }

        self.loaded = True
        self.save()
        log.info("Built index with %d documents, vocabulary size %d", len(self.documents), len(self.vocabulary))

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search index using cosine similarity."""
        if not self.loaded or not self.documents:
            return []

        # Tokenize query and compute vector
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        query_vector = vector_from_tokens(query_tokens, self.idf)

        # Compute similarity with each document
        results = []
        for doc_path, doc_data in self.documents.items():
            similarity = cosine_similarity(query_vector, doc_data["vector"])
            results.append(
                {
                    "path": doc_data["path"],
                    "similarity": float(similarity),
                    "preview": doc_data["preview"],
                    "token_count": doc_data["token_count"],
                }
            )

        # Sort by similarity descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        """Return index statistics."""
        return {
            "documents": len(self.documents),
            "vocabulary_size": len(self.vocabulary),
            "index_path": str(self.index_path),
            "loaded": self.loaded,
        }


# ---------------------------------------------------------------------------
# Tool interface (to be registered in intelligence_tools.py)
# ---------------------------------------------------------------------------


def _embed_text_simple(ctx, text: str) -> str:
    """Generate a simple TF-IDF embedding for given text (no external dependencies)."""
    if not text or not text.strip():
        return json.dumps({"error": "Empty text provided", "embedding": None})

    # For a single text, we cannot compute IDF; we'll use a dummy IDF of 1 for all words.
    # Better: use a pre-computed IDF from a default corpus (e.g., common English words).
    # For simplicity, we'll just return a bag-of-words vector with term frequencies.
    tokens = tokenize(text)
    tf = compute_tf(tokens)
    # Convert to a list representation (vocabulary may be huge, so we keep as dict)
    return json.dumps(
        {
            "text": text[:100] + ("..." if len(text) > 100 else ""),
            "embedding_type": "tf",
            "embedding": tf,
            "vocabulary_size": len(tf),
            "note": "Term frequency vector (not TF-IDF) - for search, use vault_semantic_search_simple with indexed corpus.",
        }
    )


def _vault_index_simple(ctx, full_reindex: bool = False) -> str:
    """Build a simple TF-IDF index of vault notes."""
    vault_dir = ctx.drive_path("vault")
    if not vault_dir.exists():
        return json.dumps({"error": "Vault directory not found", "indexed": 0})

    index_path = ctx.drive_path("state") / "vault_simple_index.json"

    index = SimpleIndex(index_path)
    if not full_reindex:
        index.load()
        if index.loaded and index.documents:
            # Incremental update: only rebuild if vault modified since last index?
            # For simplicity, we rebuild each time; but we can add hash checking later.
            pass

    index.build_from_vault(vault_dir)
    stats = index.get_stats()
    return json.dumps(
        {
            "status": "success",
            "indexed": stats["documents"],
            "vocabulary_size": stats["vocabulary_size"],
            "index_path": stats["index_path"],
            "full_reindex": full_reindex,
        }
    )


def _vault_search_simple(ctx, query: str, top_k: int = 5) -> str:
    """Search vault notes using simple TF-IDF and cosine similarity."""
    if not query or not query.strip():
        return json.dumps({"error": "Empty query provided", "results": []})

    index_path = ctx.drive_path("state") / "vault_simple_index.json"
    if not index_path.exists():
        return json.dumps(
            {
                "error": "Index not found. Run vault_index_simple first.",
                "results": [],
            }
        )

    index = SimpleIndex(index_path)
    index.load()
    if not index.loaded:
        return json.dumps(
            {
                "error": "Failed to load index. Run vault_index_simple again.",
                "results": [],
            }
        )

    results = index.search(query, top_k)
    # Add a note about the similarity type
    for r in results:
        r["similarity_type"] = "cosine_tfidf"
        r["note"] = "Similarity ranges from 0 (no match) to 1 (perfect match)."
    return json.dumps(
        {
            "query": query[:100] + ("..." if len(query) > 100 else ""),
            "results_count": len(results),
            "results": results,
        }
    )
