"""AI Code Generation Tool - Jo's autonomous code generation capability.

This tool enables Jo to generate, edit, and refactor code using Jo's own LLM.
No external API keys required - uses Jo's existing OpenRouter/Ollama infrastructure.

Features:
- Read existing code context
- Generate new code from descriptions
- Edit existing files with precision
- Handle multi-file changes
- Preview changes before applying
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.tools.registry import ToolEntry, ToolContext

log = logging.getLogger(__name__)


def _is_protected_file(path: str) -> bool:
    """Check if a file is protected and cannot be modified without approval."""
    protected_file = pathlib.Path(".jo_protected")
    if not protected_file.exists():
        return False

    try:
        protected_list = protected_file.read_text(encoding="utf-8").splitlines()
        # Normalize path for comparison
        normalized_path = path.replace("\\", "/").strip("./").lower()
        for protected in protected_list:
            protected = protected.strip()
            if protected and not protected.startswith("#"):
                protected_normalized = protected.replace("\\", "/").strip("./").lower()
                # Exact match
                if normalized_path == protected_normalized:
                    return True
                # Directory prefix match
                if protected_normalized.endswith("/") and normalized_path.startswith(protected_normalized):
                    return True
    except Exception:
        log.debug("Unexpected error", exc_info=True)
    return False


SYSTEM_PROMPT = """You are an expert Python programmer generating code for the Jo project.

Rules:
1. Follow existing code style and conventions
2. Use type hints where appropriate
3. Add docstrings for functions/classes
4. Keep functions under 100 lines
5. Handle errors gracefully
6. No TODO comments - implement it properly or note the limitation

Output format for file edits:
```json
{
  "files": [
    {
      "path": "relative/path/to/file.py",
      "action": "create|edit|delete",
      "content": "full file content for create/edit",
      "description": "brief description of changes"
    }
  ]
}
```

For simple edits to existing files, use "edit" action with the full new content.
For new files, use "create" action."""


def _call_jo_llm(
    prompt: str,
    system_prompt: str = SYSTEM_PROMPT,
    max_tokens: int = 8192,
) -> Optional[str]:
    """Call Jo's own LLM for code generation."""
    try:
        from ouroboros.llm import LLMClient

        client = LLMClient()
        model = "openrouter/free"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        msg, _ = client.chat(messages, model=model, max_tokens=max_tokens)
        return msg.get("content", "")

    except Exception as e:
        log.warning(f"Jo LLM call failed: {e}")
        return None


def _read_file_context(file_path: pathlib.Path, max_lines: int = 200) -> str:
    """Read file with context limit."""
    if not file_path.exists():
        return ""

    try:
        content = file_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        if len(lines) > max_lines:
            content = "\n".join(lines[:max_lines]) + f"\n\n... [{len(lines) - max_lines} more lines truncated]"
        return content
    except Exception:
        return ""


def _generate_code_edit(
    ctx: ToolContext,
    prompt: str,
    context_files: Optional[List[str]] = None,
    target_file: str = "",
) -> str:
    """Generate code edits using AI."""
    log.info(f"AI code generation: {prompt[:100]}...")

    # Check if target file is protected
    if target_file and _is_protected_file(target_file):
        return f"⚠️ PROTECTED_FILE: {target_file} is protected and cannot be modified without human approval. Ask the creator first."

    context_parts = ["## User Request\n\n" + prompt]

    if context_files:
        context_parts.append("\n\n## Relevant Code Context\n")
        for f in context_files:
            file_path = ctx.repo_dir / f
            if file_path.exists():
                rel_path = str(file_path.relative_to(ctx.repo_dir))
                content = _read_file_context(file_path)
                context_parts.append(f"\n### File: {rel_path}\n```python\n{content}\n```\n")

    if target_file:
        context_parts.append(f"\n### Target File: {target_file}\n")
        target_path = ctx.repo_dir / target_file
        if target_path.exists():
            content = _read_file_context(target_path)
            context_parts.append(f"Existing content:\n```python\n{content}\n```\n")

    full_prompt = "\n".join(context_parts)

    response = _call_jo_llm(full_prompt)
    if not response:
        return "⚠️ Jo's code generation failed. Make sure OpenRouter is accessible."

    return _parse_and_apply(response, ctx, target_file)


def _parse_and_apply(response: str, ctx: ToolContext, default_file: str = "") -> str:
    """Parse AI response and apply changes."""
    result_lines = ["## AI Code Generation Results\n"]

    try:
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            changes = json.loads(json_match.group(1))
            files = changes.get("files", [])
        else:
            code_blocks = re.findall(r"```(?:python)?\s*(.*?)\s*```", response, re.DOTALL)
            if code_blocks and default_file:
                files = [{"path": default_file, "action": "create", "content": code_blocks[0]}]
            else:
                files = []

        if not files:
            result_lines.append("### Generated Code\n")
            result_lines.append("```python\n")
            result_lines.append(response)
            result_lines.append("```\n")
            return "\n".join(result_lines)

        applied = []
        failed = []

        for f in files:
            path = f.get("path", default_file)
            action = f.get("action", "create")
            content = f.get("content", "")
            description = f.get("description", "")

            if not path:
                continue

            try:
                file_path = ctx.repo_dir / path

                if action == "delete":
                    if file_path.exists():
                        file_path.unlink()
                        applied.append(f"Deleted: {path}")
                elif action == "edit" or action == "create":
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")
                    applied.append(f"{'Updated' if action == 'edit' else 'Created'}: {path}")

                    if description:
                        result_lines.append(f"- {description}")
            except Exception as e:
                failed.append(f"{path}: {e}")

        result_lines.append("\n### Changes Applied\n")
        for msg in applied:
            result_lines.append(f"- ✅ {msg}")

        if failed:
            result_lines.append("\n### Failed\n")
            for msg in failed:
                result_lines.append(f"- ❌ {msg}")

        result_lines.append(f"\n_Generated by Jo's LLM_")

        return "\n".join(result_lines)

    except json.JSONDecodeError as e:
        log.warning(f"Failed to parse JSON from AI response: {e}")
        result_lines.append("### Generated Code\n")
        result_lines.append("```python\n")
        result_lines.append(response)
        result_lines.append("```\n")
        return "\n".join(result_lines)


def _preview_code_change(ctx: ToolContext, prompt: str, target_file: str = "") -> str:
    """Preview what code changes would look like without applying them."""
    log.info(f"Previewing code change: {prompt[:100]}...")

    context_parts = [f"## Preview Request\n\n{prompt}\n\nNOTE: This is a PREVIEW only. Do not apply changes.\n"]

    if target_file:
        target_path = ctx.repo_dir / target_file
        if target_path.exists():
            content = _read_file_context(target_path)
            context_parts.append(f"\n### Existing file: {target_file}\n```python\n{content}\n```\n")

    full_prompt = "\n".join(context_parts)

    response = _call_jo_llm(full_prompt)
    if not response:
        return "⚠️ Jo's code generation failed. Make sure OpenRouter is accessible."

    lines = ["## Code Change Preview\n", "### Proposed Changes\n", response]
    lines.append("\n_Use `ai_code_edit` to apply these changes._")

    return "\n".join(lines)


def _ai_code_edit(
    ctx: ToolContext,
    prompt: str,
    context_files: str = "",
    target_file: str = "",
    preview_only: bool = False,
) -> str:
    """Edit or create code using AI generation.

    Args:
        prompt: Description of what code to write/modify
        context_files: Comma-separated list of files to read as context
        target_file: File to edit/create (defaults to inferring from prompt)
        preview_only: If true, show diff without applying changes
    """
    if preview_only:
        return _preview_code_change(ctx, prompt, target_file)

    files = []
    if context_files:
        files = [f.strip() for f in context_files.split(",") if f.strip()]

    return _generate_code_edit(ctx, prompt, files, target_file)


def _refactor_code(ctx: ToolContext, prompt: str, target_file: str) -> str:
    """Refactor existing code with AI assistance.

    Focuses on improving code quality, readability, and maintainability.
    """
    log.info(f"Refactoring code: {target_file}")

    # Check if target file is protected
    if _is_protected_file(target_file):
        return f"⚠️ PROTECTED_FILE: {target_file} is protected and cannot be modified without human approval. Ask the creator first."

    file_path = ctx.repo_dir / target_file
    if not file_path.exists():
        return f"⚠️ File not found: {target_file}"

    content = _read_file_context(file_path)

    refactor_prompt = f"""## Refactoring Request

{prompt}

### File to Refactor: {target_file}

```python
{content}
```

Rules:
1. Preserve all functionality
2. Improve code quality and readability
3. Add type hints
4. Better error handling
5. Follow PEP 8

Output ONLY the refactored code in a JSON block.
"""

    response = _call_jo_llm(refactor_prompt)
    if not response:
        return "⚠️ Jo's refactoring failed. Make sure OpenRouter is accessible."

    return _parse_and_apply(response, ctx, target_file)


def _explain_code(ctx: ToolContext, target_file: str, focus_area: str = "") -> str:
    """Get AI explanation of code.

    Useful for understanding complex code or undocumented functions.
    """
    log.info(f"Explaining code: {target_file}")

    file_path = ctx.repo_dir / target_file
    if not file_path.exists():
        return f"⚠️ File not found: {target_file}"

    content = _read_file_context(file_path, max_lines=500)

    focus = f"\n\nFocus area: {focus_area}" if focus_area else ""

    explain_prompt = f"""## Code Explanation Request{focus}

### File: {target_file}

```python
{content}
```

Provide:
1. Brief overview of what this code does
2. Key functions and their purpose
3. Data flow
4. Potential issues or improvements{focus}
"""

    response = _call_jo_llm(explain_prompt, max_tokens=4096)
    if not response:
        return "⚠️ Jo's code explanation failed. Make sure OpenRouter is accessible."

    lines = [f"## Code Explanation: {target_file}", "", response]
    return "\n".join(lines)


def get_tools() -> List[ToolEntry]:
    """Get AI code generation tools."""
    return [
        ToolEntry(
            name="ai_code_edit",
            schema={
                "name": "ai_code_edit",
                "description": (
                    "Generate or edit code using Jo's own LLM. Jo can now write code autonomously! "
                    "Provide a description of what code to create or modify. "
                    "Jo will generate appropriate code and apply it. "
                    "Use 'preview_only=true' to see changes before applying."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Description of what code to write/modify",
                        },
                        "context_files": {
                            "type": "string",
                            "description": "Comma-separated list of files to read as context",
                        },
                        "target_file": {
                            "type": "string",
                            "description": "File to edit or create",
                        },
                        "preview_only": {
                            "type": "boolean",
                            "description": "If true, show changes without applying them",
                            "default": False,
                        },
                    },
                    "required": ["prompt"],
                },
            },
            handler=_ai_code_edit,
            is_code_tool=True,
            timeout_sec=120,
        ),
        ToolEntry(
            name="ai_code_refactor",
            schema={
                "name": "ai_code_refactor",
                "description": (
                    "Refactor existing code with AI assistance. "
                    "Improves code quality, readability, and maintainability "
                    "while preserving all functionality."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Specific refactoring goals (e.g., 'add type hints', 'improve error handling')",
                        },
                        "target_file": {
                            "type": "string",
                            "description": "File to refactor",
                        },
                    },
                    "required": ["prompt", "target_file"],
                },
            },
            handler=_refactor_code,
            is_code_tool=True,
            timeout_sec=120,
        ),
        ToolEntry(
            name="ai_code_explain",
            schema={
                "name": "ai_code_explain",
                "description": (
                    "Get AI explanation of code. "
                    "Useful for understanding complex code, undocumented functions, "
                    "or unfamiliar patterns."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_file": {
                            "type": "string",
                            "description": "File to explain",
                        },
                        "focus_area": {
                            "type": "string",
                            "description": "Specific area to focus explanation on",
                        },
                    },
                    "required": ["target_file"],
                },
            },
            handler=_explain_code,
            is_code_tool=False,
            timeout_sec=60,
        ),
    ]
