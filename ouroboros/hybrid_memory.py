"""
Ouroboros — Hybrid Memory System.

Three-layer memory architecture:
  Layer 1: Session Buffer (in-memory ring buffer + JSONL snapshot)
  Layer 2: Compression Engine (LLM fact extraction + embedding)
  Layer 3: Semantic Retrieval (vector search → context injection)

Fails soft: if embeddings/LLM unavailable, Jo continues with existing memory.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# --- Configuration defaults ---
SESSION_SIZE = 50
COMPRESS_MIN_MESSAGES = 2
RETRIEVE_TOP_K = 5
SIMILARITY_THRESHOLD = 0.92
EMBEDDING_DIMENSION = 1024
MAX_FACT_AGE_SEC = 30 * 24 * 3600  # 30 days
MAX_FACTS = 5000


@dataclass
class MemoryFact:
    """A compressed fact extracted from conversation."""

    id: str = ""
    fact: str = ""
    keywords: List[str] = field(default_factory=list)
    persons: List[str] = field(default_factory=list)
    timestamp: str = ""
    topic: str = ""
    session_key: str = ""
    created_at: float = 0.0
    vector: Optional[List[float]] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()


class _SimpleVectorStore:
    """Minimal vector store using JSONL persistence + numpy cosine similarity.

    Replaces LanceDB to keep dependencies minimal. Stores vectors in memory
    and persists to JSONL. Suitable for <10k facts.
    """

    def __init__(self, path: pathlib.Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._facts: List[MemoryFact] = []
        self._lock = threading.Lock()
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        if self.path.exists():
            try:
                now = time.time()
                with open(self.path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        fact = MemoryFact(**data)
                        # Skip expired facts
                        if fact.created_at and (now - fact.created_at) > MAX_FACT_AGE_SEC:
                            continue
                        self._facts.append(fact)
                # Enforce max limit (keep most recent)
                if len(self._facts) > MAX_FACTS:
                    self._facts = self._facts[-MAX_FACTS:]
                # Rewrite file if we filtered anything
                if self.path.exists():
                    self._rewrite()
            except Exception:
                log.warning("Failed to load vector store from %s", self.path, exc_info=True)
        self._loaded = True

    def _rewrite(self):
        """Rewrite the entire JSONL file with current facts."""
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                for fact in self._facts:
                    f.write(json.dumps(asdict(fact), ensure_ascii=False) + "\n")
        except Exception:
            log.debug("Failed to rewrite vector store", exc_info=True)

    def add(self, fact: MemoryFact) -> bool:
        """Add a fact. Deduplicates by cosine similarity threshold."""
        with self._lock:
            self._ensure_loaded()
            if fact.vector and self._facts:
                for existing in self._facts:
                    if existing.vector:
                        sim = _cosine_similarity(fact.vector, existing.vector)
                        if sim >= SIMILARITY_THRESHOLD:
                            log.debug("Skipping duplicate fact (sim=%.3f): %s", sim, fact.fact[:60])
                            return False
            self._facts.append(fact)
            self._persist(fact)
            return True

    def search(self, query_vector: List[float], top_k: int = 5) -> List[Tuple[MemoryFact, float]]:
        """Search by cosine similarity. Returns (fact, score) pairs."""
        with self._lock:
            self._ensure_loaded()
            if not self._facts or not query_vector:
                return []

            scored = []
            for fact in self._facts:
                if fact.vector:
                    sim = _cosine_similarity(query_vector, fact.vector)
                    scored.append((fact, sim))

            scored.sort(key=lambda x: x[1], reverse=True)
            return scored[:top_k]

    def count(self) -> int:
        with self._lock:
            self._ensure_loaded()
            return len(self._facts)

    def _persist(self, fact: MemoryFact):
        """Append a single fact to JSONL."""
        try:
            data = asdict(fact)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception:
            log.warning("Failed to persist fact", exc_info=True)


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors (no numpy dependency)."""
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(len(a)):
        dot += a[i] * b[i]
        norm_a += a[i] * a[i]
        norm_b += b[i] * b[i]
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / ((norm_a**0.5) * (norm_b**0.5))


def _hash_to_vector(text: str, dimension: int = EMBEDDING_DIMENSION) -> List[float]:
    """Deterministic fallback embedding using text hashing.

    NOT a real embedding — just enough for deduplication and basic similarity.
    Real embeddings come from the API when available.
    """
    vec = [0.0] * dimension
    for i, char in enumerate(text):
        h = hashlib.sha256(f"{i}:{char}".encode()).digest()
        for j in range(min(8, dimension - (i % dimension))):
            idx = (i + j) % dimension
            vec[idx] += (h[j] / 255.0) - 0.5
    # Normalize
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


class HybridMemory:
    """Three-layer hybrid memory system for Jo.

    Layer 1: Session buffer (ring buffer of recent messages)
    Layer 2: Compression (LLM extracts facts, embeds them)
    Layer 3: Retrieval (vector search for relevant context)
    """

    def __init__(self, drive_root: pathlib.Path, session_size: int = SESSION_SIZE):
        self.drive_root = drive_root
        self.session_size = session_size

        # Layer 1: Session buffer
        self._session: List[Dict[str, str]] = []
        self._session_lock = threading.Lock()
        self._session_path = drive_root / "memory" / "session.jsonl"

        # Layer 2+3: Vector store
        self._store = _SimpleVectorStore(drive_root / "memory" / "facts.jsonl")

        # Embedding client (lazy init)
        self._embed_client = None
        self._embed_model = os.environ.get("HYBRID_MEMORY_EMBED_MODEL", "text-embedding-3-small")
        self._enabled = self._check_enabled()

        # Compression state
        self._compress_thread: Optional[threading.Thread] = None
        self._compress_running = False
        self._session_key = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

        # Load persisted session
        self._load_session()

    def _check_enabled(self) -> bool:
        """Check if hybrid memory should be active."""
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            log.info("Hybrid memory disabled: no OPENROUTER_API_KEY")
            return False
        return True

    def _get_embed_client(self):
        """Lazy-init embedding client."""
        if self._embed_client is not None:
            return self._embed_client
        try:
            from openai import OpenAI

            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            self._embed_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            return self._embed_client
        except Exception as e:
            log.debug("Failed to init embedding client: %s", e)
            return None

    def _embed(self, text: str) -> List[float]:
        """Generate embedding for text. Falls back to hash-based vector."""
        client = self._get_embed_client()
        if client is None:
            return _hash_to_vector(text)
        try:
            resp = client.embeddings.create(input=text[:8000], model=self._embed_model)
            return resp.data[0].embedding
        except Exception as e:
            log.debug("Embedding API failed, using hash fallback: %s", e)
            return _hash_to_vector(text)

    # --- Layer 1: Session Buffer ---

    def add_message(self, role: str, text: str) -> None:
        """Add a message to the session buffer."""
        if not text or len(text) < 5:
            return
        msg = {"role": role, "text": text[:2000], "ts": time.time()}
        with self._session_lock:
            self._session.append(msg)
            overflow = []
            if len(self._session) > self.session_size:
                overflow = self._session[: -self.session_size]
                self._session = self._session[-self.session_size :]
            self._persist_session()

        # Trigger compression for evicted messages
        if overflow and len(overflow) >= COMPRESS_MIN_MESSAGES:
            self._schedule_compression(overflow)

    def get_session(self) -> List[Dict[str, str]]:
        """Get current session buffer."""
        with self._session_lock:
            return list(self._session)

    def _load_session(self):
        """Load session from disk."""
        if not self._session_path.exists():
            return
        try:
            lines = self._session_path.read_text(encoding="utf-8").strip().split("\n")
            for line in lines[-self.session_size :]:
                line = line.strip()
                if not line:
                    continue
                self._session.append(json.loads(line))
        except Exception:
            log.debug("Failed to load session", exc_info=True)

    def _persist_session(self):
        """Persist session buffer to disk."""
        try:
            self._session_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._session_path, "w", encoding="utf-8") as f:
                for msg in self._session:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        except Exception:
            log.debug("Failed to persist session", exc_info=True)

    # --- Layer 2: Compression ---

    def _schedule_compression(self, messages: List[Dict[str, str]]):
        """Schedule background compression of evicted messages."""
        if self._compress_thread and self._compress_thread.is_alive():
            return  # Already compressing
        self._compress_thread = threading.Thread(
            target=self._compress_messages,
            args=(messages,),
            daemon=True,
            name="hybrid-memory-compress",
        )
        self._compress_thread.start()

    def _compress_messages(self, messages: List[Dict[str, str]]):
        """Extract facts from messages using LLM, then store with embeddings."""
        if not self._enabled:
            return

        # Filter to user+assistant text only
        filtered = [m for m in messages if m.get("role") in ("user", "assistant") and len(m.get("text", "")) > 10]
        if not filtered:
            return

        # Build conversation text
        conv_lines = []
        for m in filtered:
            role = m.get("role", "unknown")
            text = m.get("text", "")[:500]
            conv_lines.append(f"{role}: {text}")
        conversation = "\n".join(conv_lines)

        # LLM extraction
        facts = self._extract_facts(conversation)
        if not facts:
            return

        # Embed and store
        for fact_data in facts:
            try:
                fact = MemoryFact(
                    fact=fact_data.get("fact", ""),
                    keywords=fact_data.get("keywords", []),
                    persons=fact_data.get("persons", []),
                    timestamp=fact_data.get("timestamp", ""),
                    topic=fact_data.get("topic", ""),
                    session_key=self._session_key,
                )
                fact.vector = self._embed(fact.fact)
                self._store.add(fact)
            except Exception:
                log.debug("Failed to process fact", exc_info=True)

        log.info("Compressed %d messages → %d facts", len(filtered), len(facts))

    def _extract_facts(self, conversation: str) -> List[Dict[str, Any]]:
        """Use LLM to extract structured facts from conversation."""
        try:
            from ouroboros.llm import LLMClient

            llm = LLMClient()
            model = os.environ.get("OUROBOROS_MODEL_LIGHT", os.environ.get("OUROBOROS_MODEL", "openrouter/free"))

            prompt = (
                "Extract structured facts from this conversation. "
                "Return a JSON array of objects with fields: fact, keywords (list), persons (list), timestamp, topic.\n"
                "Only extract concrete facts, decisions, preferences, or important context. "
                "Skip greetings, tool outputs, and generic responses.\n"
                "If no meaningful facts, return empty array [].\n\n"
                f"Conversation:\n{conversation[:3000]}\n\n"
                "JSON:"
            )

            msg, _usage = llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                max_tokens=1024,
            )

            content = msg.get("content", "")
            if not content:
                return []

            # Parse JSON from response
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            # Find JSON array in response
            start = content.find("[")
            end = content.rfind("]") + 1
            if start == -1 or end <= start:
                return []

            facts = json.loads(content[start:end])
            if isinstance(facts, list):
                return [f for f in facts if isinstance(f, dict) and f.get("fact")]
            return []
        except Exception as e:
            log.debug("Fact extraction failed: %s", e)
            return []

    # --- Layer 3: Retrieval ---

    def retrieve(self, query: str, top_k: int = RETRIEVE_TOP_K) -> str:
        """Retrieve relevant facts for a query. Returns formatted string for context injection."""
        if not query or len(query) < 5:
            return ""

        fact_count = self._store.count()
        if fact_count == 0:
            return ""

        try:
            query_vector = self._embed(query)
            results = self._store.search(query_vector, top_k=top_k)
            if not results:
                return ""

            lines = ["## Relevant Memories"]
            for fact, score in results:
                ts_str = f" ({fact.timestamp})" if fact.timestamp else ""
                topic_str = f" [{fact.topic}]" if fact.topic else ""
                lines.append(f"- {fact.fact}{ts_str}{topic_str} (relevance: {score:.2f})")

            return "\n".join(lines)
        except Exception as e:
            log.debug("Memory retrieval failed: %s", e)
            return ""

    # --- Management ---

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        with self._session_lock:
            session_len = len(self._session)
        return {
            "enabled": self._enabled,
            "session_messages": session_len,
            "stored_facts": self._store.count(),
            "session_key": self._session_key,
            "embed_model": self._embed_model,
        }

    def clear(self):
        """Clear all memory (session + facts)."""
        with self._session_lock:
            self._session.clear()
            self._persist_session()
        # Facts file is append-only; clear by deleting
        facts_path = self.drive_root / "memory" / "facts.jsonl"
        if facts_path.exists():
            facts_path.unlink()
        self._store = _SimpleVectorStore(facts_path)
        log.info("Hybrid memory cleared")


# --- Singleton ---

_instance: Optional[HybridMemory] = None
_instance_lock = threading.Lock()


def get_hybrid_memory(drive_root: Optional[pathlib.Path] = None) -> Optional[HybridMemory]:
    """Get or create the singleton HybridMemory instance."""
    global _instance
    if _instance is not None:
        return _instance
    if drive_root is None:
        return None
    with _instance_lock:
        if _instance is None:
            _instance = HybridMemory(drive_root)
    return _instance
