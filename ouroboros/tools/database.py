"""
Database tools - SQLite for structured memory.
No external dependencies - uses Python standard library only.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
from typing import Any, List, Optional

from ouroboros.tools.registry import ToolContext, ToolEntry


def _get_db_path(ctx: ToolContext) -> pathlib.Path:
    """Get or create database path in Jo's data directory."""
    db_dir = ctx.drive_root / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "jo_memory.db"


def _db_query(ctx: ToolContext, query: str, params: Optional[List[Any]] = None) -> str:
    """Execute a SELECT query and return results."""
    db_path = _get_db_path(ctx)

    if not db_path.exists():
        return "⚠️ Database not initialized. Use db_init first."

    params = params or []
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query, params)

        if query.strip().upper().startswith("SELECT"):
            rows = cur.fetchall()
            if not rows:
                return "No results."

            # Format as table
            columns = list(rows[0].keys())
            result = [", ".join(columns)]
            for row in rows:
                result.append(", ".join(str(row[col]) for col in columns))

            conn.close()
            return "\n".join(result[:20])  # Limit output
        else:
            conn.commit()
            conn.close()
            return f"✅ Query executed. Rows affected: {cur.rowcount}"

    except sqlite3.Error as e:
        return f"⚠️ Database error: {e}"


def _db_write(ctx: ToolContext, table: str, data: str, key_field: str = "id") -> str:
    """Insert or update a record in a table.

    data: JSON object with fields to insert/update.
    """
    db_path = _get_db_path(ctx)

    try:
        data_obj = json.loads(data)
    except json.JSONDecodeError:
        return "⚠️ Invalid JSON. Provide data as JSON object."

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        # Get existing columns
        cur.execute(f"PRAGMA table_info({table})")
        columns = {row[1] for row in cur.fetchall()}

        # Filter data_obj to existing columns
        filtered = {k: v for k, v in data_obj.items() if k in columns}

        if not filtered:
            return f"⚠️ No valid fields for table {table}. Available: {columns}"

        # Check if record exists
        if key_field in filtered:
            cur.execute(f"SELECT 1 FROM {table} WHERE {key_field} = ?", (filtered[key_field],))
            exists = cur.fetchone() is not None
        else:
            exists = False

        if exists:
            # Update
            set_clause = ", ".join(f"{k} = ?" for k in filtered.keys())
            values = list(filtered.values())
            cur.execute(f"UPDATE {table} SET {set_clause} WHERE {key_field} = ?", values + [filtered[key_field]])
        else:
            # Insert
            cols = ", ".join(filtered.keys())
            placeholders = ", ".join(["?"] * len(filtered))
            cur.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", list(filtered.values()))

        conn.commit()
        conn.close()
        return f"✅ Saved to {table}"

    except sqlite3.Error as e:
        return f"⚠️ Database error: {e}"
    except Exception as e:
        return f"⚠️ Error: {e}"


def _db_init(ctx: ToolContext, schema: str) -> str:
    """Initialize database tables.

    schema: JSON object with table definitions.
    Example: {"tasks": {"id": "TEXT PRIMARY KEY", "status": "TEXT", "created_at": "TEXT"}}
    """
    db_path = _get_db_path(ctx)

    try:
        schema_obj = json.loads(schema)
    except json.JSONDecodeError:
        return "⚠️ Invalid JSON. Provide schema as JSON object."

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        for table_name, columns in schema_obj.items():
            # Build CREATE TABLE statement
            col_defs = []
            for col_name, col_type in columns.items():
                col_defs.append(f"{col_name} {col_type}")

            create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)})"
            cur.execute(create_sql)

        conn.commit()
        conn.close()
        return f"✅ Database initialized with tables: {list(schema_obj.keys())}"

    except sqlite3.Error as e:
        return f"⚠️ Database error: {e}"
    except Exception as e:
        return f"⚠️ Error: {e}"


def _db_list_tables(ctx: ToolContext) -> str:
    """List all tables in the database."""
    db_path = _get_db_path(ctx)

    if not db_path.exists():
        return "⚠️ Database not initialized."

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        conn.close()

        if not tables:
            return "No tables found. Use db_init to create tables."

        return "Tables:\n" + "\n".join(f"- {t}" for t in tables)

    except sqlite3.Error as e:
        return f"⚠️ Error: {e}"


def _db_schema_read(ctx: ToolContext, table: str) -> str:
    """Read the schema of a table."""
    db_path = _get_db_path(ctx)

    if not db_path.exists():
        return "⚠️ Database not initialized."

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        columns = cur.fetchall()
        conn.close()

        if not columns:
            return f"⚠️ Table '{table}' not found."

        result = [f"Table: {table}"]
        for col in columns:
            result.append(f"  {col[1]}: {col[2]}" + (" PRIMARY KEY" if col[5] else ""))

        return "\n".join(result)

    except sqlite3.Error as e:
        return f"⚠️ Error: {e}"


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            "db_query",
            {
                "name": "db_query",
                "description": "Execute a SELECT query on Jo's structured memory database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "SQL SELECT query"},
                        "params": {"type": "array", "description": "Query parameters", "items": {"type": "string"}},
                    },
                    "required": ["query"],
                },
            },
            _db_query,
        ),
        ToolEntry(
            "db_write",
            {
                "name": "db_write",
                "description": "Insert or update a record in a database table.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Table name"},
                        "data": {"type": "string", "description": "JSON object with fields to save"},
                        "key_field": {"type": "string", "default": "id", "description": "Primary key field for upsert"},
                    },
                    "required": ["table", "data"],
                },
            },
            _db_write,
        ),
        ToolEntry(
            "db_init",
            {
                "name": "db_init",
                "description": "Initialize database tables. Example schema: {'tasks': {'id': 'TEXT PRIMARY KEY', 'status': 'TEXT'}}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "schema": {"type": "string", "description": "JSON object defining tables and columns"},
                    },
                    "required": ["schema"],
                },
            },
            _db_init,
        ),
        ToolEntry(
            "db_list_tables",
            {
                "name": "db_list_tables",
                "description": "List all tables in the database.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            _db_list_tables,
        ),
        ToolEntry(
            "db_schema_read",
            {
                "name": "db_schema_read",
                "description": "Read the schema (columns) of a table.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string", "description": "Table name"},
                    },
                    "required": ["table"],
                },
            },
            _db_schema_read,
        ),
    ]
