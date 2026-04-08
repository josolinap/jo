"""Agent capability indexing for Jo.

Builds a compressed manifest of tools, skills, and workflows for efficient
discovery and routing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

class AgentIndex:
    """Manages the agent's capability manifest."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.index_path = repo_dir / ".jo_state" / "agent_index.json"

    def build(self, tool_registry: Any) -> Dict[str, Any]:
        """Build the manifest from current tools and skills."""
        manifest = {
            "version": "1.0",
            "tools": [],
            "skills": [],
            "workflows": []
        }

        # 1. Index Tools
        try:
            for schema in tool_registry.schemas():
                name = schema["function"]["name"]
                desc = schema["function"]["description"].split("\n")[0]
                
                # Assign cost tiers (heuristic)
                tier = "CHEAP"
                if any(x in name for x in ["search", "analyze", "list", "read", "browse"]):
                    tier = "MEDIUM"
                if any(x in name for x in ["commit", "push", "write", "edit"]):
                    tier = "EXPENSIVE"
                
                manifest["tools"].append({
                    "name": name,
                    "desc": desc[:100],
                    "tier": tier
                })
        except Exception as e:
            log.warning(f"Failed to index tools: {e}")

        # 2. Index Skills
        skills_path = self.repo_dir / ".jo_skills"
        if skills_path.exists():
            for skill_dir in skills_path.iterdir():
                if skill_dir.is_dir():
                    manifest["skills"].append(skill_dir.name)

        # 3. Index Workflows
        workflows_path = self.repo_dir / ".agents" / "workflows"
        if workflows_path.exists():
            for wf_file in workflows_path.glob("*.md"):
                manifest["workflows"].append(wf_file.stem)

        # Save to disk
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self.index_path.write_text(json.dumps(manifest, indent=2))
        except Exception:
            pass

        return manifest

    def get_summary(self) -> str:
        """Return a compressed string summary for context usage."""
        if not self.index_path.exists():
            return "[AGENT_INDEX] No index built yet."
        
        try:
            data = json.loads(self.index_path.read_text())
            tools_count = len(data.get("tools", []))
            skills_count = len(data.get("skills", []))
            workflows_count = len(data.get("workflows", []))
            
            # Group tools by tier for brevity
            tiers = {"CHEAP": 0, "MEDIUM": 0, "EXPENSIVE": 0}
            for t in data.get("tools", []):
                tiers[t["tier"]] = tiers.get(t["tier"], 0) + 1

            return (
                f"[AGENT_INDEX] v{data.get('version')} | "
                f"Tools: {tools_count} ({tiers['CHEAP']}C/{tiers['MEDIUM']}M/{tiers['EXPENSIVE']}E) | "
                f"Skills: {skills_count} | Workflows: {workflows_count}"
            )
        except Exception:
            return "[AGENT_INDEX] Error reading manifest."

def get_agent_index(repo_dir: Path) -> AgentIndex:
    return AgentIndex(repo_dir)
