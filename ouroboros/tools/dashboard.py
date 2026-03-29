from typing import Dict, Any, List
import logging
import os
import json
import datetime
from ouroboros.tools.registry import ToolContext

log = logging.getLogger(__name__)


def get_runtime_state(ctx):
    p = ctx.drive_path("state/state.json")
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except:
            pass
    return {}


def get_tool_usage(ctx):
    usage = {}
    p = ctx.drive_path("logs/events.jsonl")
    if p.exists():
        try:
            for line in p.read_text(encoding="utf-8").splitlines()[-5000:]:
                try:
                    ev = json.loads(line)
                    if ev.get("type") == "tool_called":
                        name = ev.get("tool", "unknown")
                        usage[name] = usage.get(name, 0) + 1
                except:
                    continue
        except:
            pass
    return usage


def system_dashboard(ctx, comprehensive=False):
    try:
        from ouroboros.tools.registry import ToolRegistry

        tr = ToolRegistry(ctx.repo_dir, ctx.drive_root)
        tc = len(tr.schemas())

        state = get_runtime_state(ctx)
        usage = get_tool_usage(ctx)

        lines = ["## System Dashboard", "- Tools: " + str(tc)]

        if state:
            lines.append("- Version: " + state.get("version", "unknown"))
            budget = float(os.environ.get("TOTAL_BUDGET", "1"))
            spent = state.get("spent_usd", 0)
            lines.append("- Budget: $" + str(spent) + "/" + str(int(budget)))

        top = sorted(usage.items(), key=lambda x: x[1], reverse=True)[:5]
        if top:
            lines.append("Top Used:")
            for n, c in top:
                lines.append("- " + n + ": " + str(c))

        return "\n".join(lines)
    except Exception as e:
        return "Error: " + str(e)


def query_tools(ctx, category="", min_usage=0, time_hours=24, search=""):
    try:
        from ouroboros.tools.registry import ToolRegistry

        tr = ToolRegistry(ctx.repo_dir, ctx.drive_root)
        all_tools = tr.schemas()

        usage = get_tool_usage(ctx)
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=time_hours)

        recent = {}
        p = ctx.drive_path("logs/events.jsonl")
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines()[-10000:]:
                try:
                    ev = json.loads(line)
                    ts = ev.get("timestamp", "")
                    if ts:
                        try:
                            ev_time = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            if ev_time < cutoff:
                                continue
                        except:
                            pass
                    if ev.get("type") == "tool_called":
                        name = ev.get("tool", "unknown")
                        recent[name] = recent.get(name, 0) + 1
                except:
                    continue

        results = []
        for t in all_tools:
            name = t.get("function", {}).get("name", "")
            desc = t.get("function", {}).get("description", "")

            if category:
                if category.lower() not in desc.lower() and category.lower() not in name.lower():
                    continue

            if search:
                if search.lower() not in desc.lower() and search.lower() not in name.lower():
                    continue

            use = recent.get(name, 0)
            if use < min_usage:
                continue

            results.append({"name": name, "desc": desc[:80], "usage": use})

        lines = ["## Query Results (" + str(len(results)) + " found)"]
        if category:
            lines.append("Category: " + category)
        if search:
            lines.append("Search: " + search)
        lines.append("Time: " + str(time_hours) + "h")
        lines.append("")

        for r in results[:30]:
            lines.append("- " + r["name"] + ": " + r["desc"] + " (used:" + str(r["usage"]) + ")")

        return "\n".join(lines)
    except Exception as e:
        return "Error: " + str(e)


def trend_analytics(ctx, metric="tool_usage", days=7):
    try:
        p = ctx.drive_path("logs/events.jsonl")
        daily = {}

        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines()[-30000:]:
                try:
                    ev = json.loads(line)
                    ts = ev.get("timestamp", "")
                    if not ts:
                        continue
                    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    d = dt.date().isoformat()
                    if d not in daily:
                        daily[d] = {"tools": 0, "tasks": 0}
                    if ev.get("type") == "tool_called":
                        daily[d]["tools"] += 1
                    elif ev.get("type") in ["task_done", "task_error"]:
                        daily[d]["tasks"] += 1
                except:
                    continue

        if metric == "tool_usage":
            lines = ["## Trend: Tool Usage (" + str(days) + " days)"]
            ds = sorted(daily.keys())[-days:]
            total = 0
            for d in ds:
                c = daily[d]["tools"]
                total += c
                lines.append("- " + d + ": " + str(c) + " calls")
            if ds:
                lines.append("Average: " + str(total // len(ds)) + "/day")

        elif metric == "task_success":
            total = sum(daily[d].get("tasks", 0) for d in daily)
            lines = ["## Trend: Task Success (" + str(days) + " days)", "- Total: " + str(total)]

        else:
            lines = ["## Predictions (" + str(days) + " days)", "- Use tool_usage or task_success metric"]

        return "\n".join(lines)
    except Exception as e:
        return "Error: " + str(e)


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    return [
        ToolEntry(
            "system_dashboard",
            {
                "name": "system_dashboard",
                "description": "Unified dashboard: tools, vault, state, budget. Use comprehensive=true for details.",
                "parameters": {
                    "type": "object",
                    "properties": {"comprehensive": {"type": "boolean", "default": False}},
                    "required": [],
                },
            },
            system_dashboard,
        ),
        ToolEntry(
            "query_tools",
            {
                "name": "query_tools",
                "description": "Query tools by category, usage, time. Eg: find vault tools used in last 24h",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "min_usage": {"type": "integer"},
                        "time_hours": {"type": "integer"},
                        "search": {"type": "string"},
                    },
                    "required": [],
                },
            },
            query_tools,
        ),
        ToolEntry(
            "trend_analytics",
            {
                "name": "trend_analytics",
                "description": "Trend analysis: tool usage patterns, task success rates",
                "parameters": {
                    "type": "object",
                    "properties": {"metric": {"type": "string"}, "days": {"type": "integer"}},
                    "required": [],
                },
            },
            trend_analytics,
        ),
    ]
