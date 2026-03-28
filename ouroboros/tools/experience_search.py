"""
Ouroboros Tool: Search Experience.
Allows Jo to query past activities to learn from historical successes and failures.
"""

from typing import Dict, Any, List
import logging
from ouroboros.tools.registry import ToolContext

log = logging.getLogger(__name__)

def search_experience(ctx: ToolContext, query: str) -> str:
    """Search the experience index for relevant past activities.
    Use this to find how similar tasks were handled in the past.
    """
    try:
        from ouroboros.experience_indexer import ExperienceIndexer
        indexer = ExperienceIndexer(ctx.drive_root)
        results = indexer.search(query)
        
        if not results:
            return "No matching past experiences found."
            
        lines = [f"Found {len(results)} relevant past experiences:"]
        for res in results:
            status = "✅ Success" if res["success"] else "❌ Failure"
            lines.append(f"- [{res['ts']}] {status}: {res['summary']} (TaskID: {res['task_id']})")
            
        return "\n".join(lines)
    except Exception as e:
        log.error(f"search_experience tool failed: {e}")
        return f"Error searching experience: {e}"
