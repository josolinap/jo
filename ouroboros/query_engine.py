import logging
import pathlib
import queue
from typing import Any, Callable, Dict, List, Optional, Tuple

from ouroboros.llm import LLMClient
from ouroboros.tools.registry import ToolRegistry
from ouroboros.loop import run_llm_loop

log = logging.getLogger(__name__)

class QueryEngine:
    """Stateful capsule managing the query lifecycle, messages, and model interaction.
    
    Inspired by claude-code-src QueryEngine.ts. This class encapsulates what was formerly
    the giant monolithic run_llm_loop function.
    """
    
    def __init__(
        self,
        messages: List[Dict[str, Any]],
        tools: ToolRegistry,
        llm: LLMClient,
        drive_logs: pathlib.Path,
        emit_progress: Callable[[str], None],
        incoming_messages: queue.Queue,
        task_type: str = "",
        task_id: str = "",
        budget_remaining_usd: Optional[float] = None,
        event_queue: Optional[queue.Queue] = None,
        initial_effort: str = "medium",
        drive_root: Optional[pathlib.Path] = None,
    ):
        self.messages = messages
        self.tools = tools
        self.llm = llm
        self.drive_logs = drive_logs
        self.emit_progress = emit_progress
        self.incoming_messages = incoming_messages
        self.task_type = task_type
        self.task_id = task_id
        self.budget_remaining_usd = budget_remaining_usd
        self.event_queue = event_queue
        self.initial_effort = initial_effort
        self.drive_root = drive_root
        
        # Internal state
        self.round_idx = 0
        self.active_model = llm.default_model()
        self.active_effort = initial_effort
        self.accumulated_usage: Dict[str, Any] = {}
        self.llm_trace: Dict[str, Any] = {"assistant_notes": [], "tool_calls": []}
        self.stateful_executor = None
        self._owner_msg_seen = set()

    def run(self) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        """Starts the main message parsing and tool execution turn loop."""
        log.info(f"[QueryEngine] Starting query lifecycle for task {self.task_id}")
        
        # Bridging to loop.py for now to avoid breaking complex dependencies,
        # but providing the instance-based state container.
        return run_llm_loop(
            messages=self.messages,
            tools=self.tools,
            llm=self.llm,
            drive_logs=self.drive_logs,
            emit_progress=self.emit_progress,
            incoming_messages=self.incoming_messages,
            task_type=self.task_type,
            task_id=self.task_id,
            budget_remaining_usd=self.budget_remaining_usd,
            event_queue=self.event_queue,
            initial_effort=self.initial_effort,
            drive_root=self.drive_root,
            engine=self,
        )

    def preflight_checks(self) -> Tuple[bool, str]:
        """Deterministic governance before LLM calls."""
        if self.budget_remaining_usd is not None and self.budget_remaining_usd <= 0:
            return False, "Budget exhausted - cannot proceed"
        return True, ""

    def drain_incoming_messages(self) -> None:
        """Inject owner messages received during task execution."""
        while not self.incoming_messages.empty():
            try:
                injected = self.incoming_messages.get_nowait()
                self.messages.append({"role": "user", "content": injected})
            except queue.Empty:
                break

        if self.drive_root is not None and self.task_id:
            from ouroboros.owner_inject import drain_owner_messages
            drive_msgs = drain_owner_messages(
                self.drive_root, 
                task_id=self.task_id, 
                seen_ids=self._owner_msg_seen
            )
            for dmsg in drive_msgs:
                self.messages.append({"role": "user", "content": f"[Owner message during task]: {dmsg}"})
                if self.event_queue is not None:
                    try:
                        self.event_queue.put_nowait({
                            "type": "owner_message_injected",
                            "task_id": self.task_id,
                            "text": dmsg[:200],
                        })
                    except Exception:
                        log.debug("Unexpected error", exc_info=True)


