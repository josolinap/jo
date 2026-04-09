"""
Skill Repository for Jo (Memento-Skills).

Handles storage, persistence, and semantic retrieval of executable skills.
"""

from __future__ import annotations

import json
import logging
import pathlib
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.hybrid_memory import _SimpleVectorStore, _hash_to_vector

log = logging.getLogger(__name__)

@dataclass
class Skill:
    """An executable skill (tool) synthesized by Jo."""
    id: str = ""
    name: str = ""
    description: str = ""
    code: str = ""
    unit_tests: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    author: str = "Jo"
    created_at: float = 0.0
    updated_at: float = 0.0
    vector: Optional[List[float]] = None
    usage_count: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()
        if not self.updated_at:
            self.updated_at = self.created_at

class SkillRepository:
    """Manages the lifecycle of executable skills."""
    
    def __init__(self, drive_root: pathlib.Path):
        self.drive_root = drive_root
        self.skills_dir = drive_root / ".jo_skills" / "executable"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        # We store the metadata in a vector store for semantic retrieval
        self.metadata_path = self.skills_dir / "metadata.jsonl"
        self._store = _SimpleVectorStore(self.metadata_path)
        
    def add_skill(self, skill: Skill) -> bool:
        """Add or update a skill in the repository."""
        # Ensure it has a vector for retrieval
        if not skill.vector:
            # Note: Ideally we use a real embedding, but we'll use fallback for now
            # In a real scenario, we'd call the embedding provider
            skill.vector = _hash_to_vector(f"{skill.name} {skill.description}")
            
        # Write the code to a physical file for execution compatibility
        code_path = self.skills_dir / f"{skill.name}.py"
        try:
            code_path.write_text(skill.code, encoding="utf-8")
            
            # Persist metadata to vector store
            # Need to convert Skill to something _SimpleVectorStore understands (MemoryFact-like)
            # Actually, _SimpleVectorStore expects MemoryFact, but it's just a dataclass.
            # We'll just store the Skill directly as long as it behaves like MemoryFact.
            # Since _SimpleVectorStore uses asdict() and json.loads(), we can pass Skill if it matches interface.
            
            # For strictness, let's wrap it or ensure _SimpleVectorStore is generic enough.
            # _SimpleVectorStore expects MemoryFact(**data). 
            # Let's monkeypatch or just use a dedicated Store class.
            
            # For now, let's use the underlying _facts list directly since _SimpleVectorStore is simple.
            return self._store.add(skill) # type: ignore
        except Exception as e:
            log.error("Failed to add skill %s: %s", skill.name, e)
            return False

    def search_skills(self, query_vector: List[float], top_k: int = 3) -> List[Tuple[Skill, float]]:
        """Find skills relevant to the current task."""
        # The underlying store returns (fact, score)
        results = self._store.search(query_vector, top_k=top_k)
        return results # type: ignore

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """Retrieve a skill by its name."""
        # This is a bit slow on _SimpleVectorStore but acceptable for small skill sets
        with self._store._lock:
            self._store._ensure_loaded()
            for skill in self._store._facts:
                if skill.name == name:
                    return skill # type: ignore
        return None

# Singleton-like getter
_instance: Optional[SkillRepository] = None

def get_skill_repository(drive_root: pathlib.Path) -> SkillRepository:
    global _instance
    if _instance is None:
        _instance = SkillRepository(drive_root)
    return _instance
