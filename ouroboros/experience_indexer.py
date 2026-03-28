"""
Ouroboros Experience Indexer — builds a searchable knowledge base from past activities.
Distills events.jsonl into a keyword-based experience index.
"""

import json
import logging
import pathlib
import re
from typing import List, Dict, Any, Set
from collections import defaultdict

log = logging.getLogger(__name__)

class ExperienceIndexer:
    def __init__(self, drive_root: pathlib.Path):
        self.drive_root = drive_root
        self.events_path = drive_root / "logs" / "events.jsonl"
        self.index_path = drive_root / "memory" / "experience_index.json"
        self.stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "is", "was", "be"}

    def rebuild(self, limit: int = 1000):
        """Rebuild the experience index from the last N events."""
        if not self.events_path.exists():
            log.warning("ExperienceIndexer: events.jsonl not found.")
            return

        index = defaultdict(list)
        try:
            with open(self.events_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        ev = json.loads(line)
                        etype = ev.get("type")
                        if etype in ("task_done", "task_error", "task_eval", "task_received"):
                            self._index_event(ev, index)
                    except:
                        continue
            
            self._save_index(index)
            log.info("ExperienceIndexer: Index rebuilt with %d keywords.", len(index))
        except Exception as e:
            log.error(f"ExperienceIndexer: Failed to rebuild index: {e}")

    def _index_event(self, ev: Dict[str, Any], index: Dict[str, List[Dict[str, Any]]]):
        # Extract meaningful text from task and results
        task_text = ""
        # Handle different event formats
        if "task" in ev and isinstance(ev["task"], dict):
            task_text = ev["task"].get("text", "") or ev["task"].get("content", "")
        
        # Result text from send_message events usually follows task_done in logs? 
        # Actually, task_done might not have the full text, but events.jsonl has it.
        
        text_to_index = f"{task_text}".lower()
        keywords = self._extract_keywords(text_to_index)
        
        entry = {
            "ts": ev.get("ts"),
            "task_id": ev.get("task_id"),
            "type": ev.get("type"),
            "summary": task_text[:100] + "..." if len(task_text) > 100 else task_text,
            "success": ev.get("type") == "task_done"
        }
        
        for kw in keywords:
            # Keep only the last 5 entries per keyword to avoid bloat
            index[kw].append(entry)
            if len(index[kw]) > 5:
                index[kw].pop(0)

    def _extract_keywords(self, text: str) -> Set[str]:
        # Simple regex word extraction
        words = re.findall(r'\b\w{3,}\b', text)
        return {w for w in words if w not in self.stop_words}

    def _save_index(self, index: Dict[str, List[Any]]):
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.index_path, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2)

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search the index for relevant past experiences."""
        if not self.index_path.exists():
            return []
            
        try:
            with open(self.index_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
            
            query_keywords = self._extract_keywords(query.lower())
            results = []
            seen_tasks = set()
            
            for kw in query_keywords:
                if kw in index:
                    for entry in index[kw]:
                        if entry["task_id"] not in seen_tasks:
                            results.append(entry)
                            seen_tasks.add(entry["task_id"])
            
            # Sort by timestamp (newest first)
            results.sort(key=lambda x: x.get("ts", ""), reverse=True)
            return results[:10]
        except Exception as e:
            log.error(f"ExperienceIndexer: Search failed: {e}")
            return []
