"""Analytics tools for Jo.

Provides insights into token savings and agent performance.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any
from ouroboros.tools.registry import ToolEntry
from ouroboros.cost_tracker import CostTracker

log = logging.getLogger(__name__)

def _handle_show_token_savings(ctx: Any, **kwargs: Any) -> str:
    tracker = CostTracker()
    report = tracker.generate_report()
    
    lines = [
        "## ⚡ Token Savings Report",
        f"- **Total Characters Saved**: {report.total_chars_saved:,}",
        f"- **Estimated Token Reduction**: ~{report.total_chars_saved // 4:,} tokens",
        f"- **Burn Rate**: ${tracker.calculate_burn_rate():.4f}/hr",
        "",
        "### Top Model Usage",
    ]
    
    for model, usage in list(report.by_model.items())[:5]:
        lines.append(f"- **{model}**: ${usage['cost']:.4f} ({usage['input_tokens'] + usage['output_tokens']:,} tokens)")
        
    return "\n".join(lines)

def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            name="show_token_savings",
            schema={
                "name": "show_token_savings",
                "description": "Show analytics on internal token compression savings and current burn rate.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            handler=_handle_show_token_savings,
        )
    ]
