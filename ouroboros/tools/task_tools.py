import uuid
import threading
from typing import Any, List
from ouroboros.tools.factory import ToolFactory
from ouroboros.tools.registry import ToolEntry

# Global task registry for background subagents
_ACTIVE_TASKS = {}
_TASK_LOCK = threading.Lock()

def _spawn_subagent(task_id: str, objective: str, original_ctx: Any):
    # Spin up an isolated pipeline/context to solve the objective
    try:
        from ouroboros.agent import make_agent
        import json
        import pathlib
        
        agent = make_agent(
            repo_dir=str(original_ctx.repo_dir), 
            drive_root=str(original_ctx.drive_root)
        )
        task = {
            "id": task_id,
            "type": "subtask",
            "text": f"[SUBAGENT OBJECTIVE]: {objective}",
            "chat_id": int(original_ctx.current_chat_id) if original_ctx.current_chat_id else 0,
            "depth": getattr(original_ctx, "task_depth", 0) + 1,
        }
        
        # This writes to drive_root / "task_results" / f"{task_id}.json"
        agent.handle_task(task)
        
        # Scrape result
        results_dir = pathlib.Path(original_ctx.drive_root) / "task_results"
        result_file = results_dir / f"{task_id}.json"
        if result_file.exists():
            data = json.loads(result_file.read_text(encoding="utf-8"))
            final_res = data.get("result", "Completed, but no result string found.")
        else:
            final_res = "Task finished, but no result file was created."
            
        with _TASK_LOCK:
            _ACTIVE_TASKS[task_id]["status"] = "completed"
            _ACTIVE_TASKS[task_id]["result"] = final_res
    except Exception as e:
        with _TASK_LOCK:
            _ACTIVE_TASKS[task_id]["status"] = "failed"
            _ACTIVE_TASKS[task_id]["result"] = str(e)



def handle_task_create(ctx: Any, objective: str, **kwargs) -> str:
    # Fork bomb protection
    if getattr(ctx, "task_depth", 0) > 2:
        return "⚠️ Subagent creation blocked: maximum recursion depth reached."
        
    task_id = str(uuid.uuid4())[:8]
    
    with _TASK_LOCK:
        _ACTIVE_TASKS[task_id] = {
            "objective": objective,
            "status": "running",
            "result": None
        }
        
    # Start subagent loop in a separate thread
    thread = threading.Thread(
        target=_spawn_subagent, 
        args=(task_id, objective, ctx)
    )
    thread.daemon = True
    thread.start()
    
    return f"Started background task {task_id}. Objective: {objective}. Use task_check to get status."

def handle_task_check(ctx: Any, task_id: str, **kwargs) -> str:
    with _TASK_LOCK:
        task = _ACTIVE_TASKS.get(task_id)
        
    if not task:
        return f"⚠️ Task {task_id} not found."
        
    if task["status"] == "running":
        return f"Task {task_id} is still running."
    else:
        # Retrieve and clear
        res = task["result"]
        return f"Task {task_id} completed with status {task['status']}:\n{res}"


# Using the new Factory pattern to build these tools!
task_create_tool = ToolFactory.build(
    name="task_create",
    description="Spawn a background subagent (clone of yourself) to accomplish an isolated objective parallel to your current thinking.",
    handler=handle_task_create,
    parameters={
        "objective": {"type": "string", "description": "The goal for the subagent to complete independently."}
    },
    required=["objective"]
)

task_check_tool = ToolFactory.build(
    name="task_check",
    description="Check the status or pull the result of an ongoing background subagent task.",
    handler=handle_task_check,
    parameters={
        "task_id": {"type": "string", "description": "The abbreviated task ID."}
    },
    required=["task_id"]
)

def get_tools() -> List[ToolEntry]:
    return [task_create_tool, task_check_tool]
