...
    st.setdefault("evolution_consecutive_failures", 0)
    st.setdefault("evolution_history", [])  # List of {task_id, cycle, timestamp, commits, success, archived}
    st.setdefault("recent_tasks", [])  # List of {task_id, type, completed_at, chat_id, text} for continuity
    for legacy_key in (
        "approvals",
        "idle_cursor",
        "idle_stats",
        "last_idle_task_at",
        "last_auto_review_at",
        "last_review_task_id",
        "session_daily_snapshot",
    ):
        st.pop(legacy_key, None)
    return st
...