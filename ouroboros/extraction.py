"""
Extraction Module - Extract structured information from unstructured text.

Inspired by Google's LangExtract library. Provides:
- Structured information extraction
- Source grounding (track where extractions came from)
- Few-shot guided extraction
- Integration with vault for storage

Key concepts:
1. Extraction: A piece of structured information with source location
2. ExampleData: Few-shot examples to guide extraction
3. Source grounding: Track exact location of each extraction
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class Extraction:
    """A single extraction with source grounding."""

    extraction_class: str  # e.g., "function", "entity", "intent", "relationship"
    extraction_text: str  # Exact text from source
    char_interval: Optional[Tuple[int, int]] = None  # (start, end) in source
    attributes: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    # Source grounding
    source_file: str = ""
    source_line: int = 0
    source_context: str = ""  # Surrounding text for context

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "class": self.extraction_class,
            "text": self.extraction_text,
            "char_interval": self.char_interval,
            "attributes": self.attributes,
            "confidence": self.confidence,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "source_context": self.source_context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Extraction:
        """Create from dictionary."""
        return cls(
            extraction_class=data.get("class", ""),
            extraction_text=data.get("text", ""),
            char_interval=tuple(data["char_interval"]) if data.get("char_interval") else None,
            attributes=data.get("attributes", {}),
            confidence=data.get("confidence", 1.0),
            source_file=data.get("source_file", ""),
            source_line=data.get("source_line", 0),
            source_context=data.get("source_context", ""),
        )


@dataclass
class ExampleData:
    """Few-shot example for guiding extraction."""

    text: str
    extractions: List[Extraction]

    def to_prompt_format(self) -> str:
        """Format for inclusion in LLM prompt."""
        lines = [f"Input: {self.text}", "Extractions:"]
        for ext in self.extractions:
            attr_str = json.dumps(ext.attributes) if ext.attributes else "{}"
            lines.append(f"  - class: {ext.extraction_class}")
            lines.append(f'    text: "{ext.extraction_text}"')
            lines.append(f"    attributes: {attr_str}")
        return "\n".join(lines)


@dataclass
class ExtractionResult:
    """Result of an extraction operation."""

    extractions: List[Extraction]
    source_text: str
    extraction_classes: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def filter_grounded(self) -> List[Extraction]:
        """Return only extractions with valid source grounding."""
        return [e for e in self.extractions if e.char_interval is not None]

    def filter_class(self, extraction_class: str) -> List[Extraction]:
        """Filter extractions by class."""
        return [e for e in self.extractions if e.extraction_class == extraction_class]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "extractions": [e.to_dict() for e in self.extractions],
            "source_text_length": len(self.source_text),
            "extraction_classes": self.extraction_classes,
            "metadata": self.metadata,
            "grounded_count": len(self.filter_grounded()),
            "total_count": len(self.extractions),
        }

    def to_markdown(self) -> str:
        """Format as markdown for vault storage."""
        lines = [
            "# Extraction Results",
            "",
            f"Source length: {len(self.source_text)} chars",
            f"Total extractions: {len(self.extractions)}",
            f"Grounded extractions: {len(self.filter_grounded())}",
            "",
        ]

        # Group by class
        by_class: Dict[str, List[Extraction]] = {}
        for ext in self.extractions:
            if ext.extraction_class not in by_class:
                by_class[ext.extraction_class] = []
            by_class[ext.extraction_class].append(ext)

        for cls, exts in sorted(by_class.items()):
            lines.append(f"## {cls.title()} ({len(exts)})")
            lines.append("")
            for ext in exts:
                source_info = ""
                if ext.source_file:
                    source_info = f" [{ext.source_file}"
                    if ext.source_line:
                        source_info += f":{ext.source_line}"
                    source_info += "]"
                elif ext.char_interval:
                    source_info = f" [chars {ext.char_interval[0]}-{ext.char_interval[1]}]"

                lines.append(f"- **{ext.extraction_text}**{source_info}")
                if ext.attributes:
                    for k, v in ext.attributes.items():
                        lines.append(f"  - {k}: {v}")
            lines.append("")

        return "\n".join(lines)


def _find_text_location(source: str, text: str) -> Optional[Tuple[int, int]]:
    """Find the location of text in source string.

    Returns (start, end) indices or None if not found.
    """
    # Try exact match first
    idx = source.find(text)
    if idx != -1:
        return (idx, idx + len(text))

    # Try normalized match (remove extra whitespace)
    normalized_source = " ".join(source.split())
    normalized_text = " ".join(text.split())
    idx = normalized_source.find(normalized_text)
    if idx != -1:
        # Map back to original indices
        original_idx = 0
        norm_idx = 0
        while norm_idx < idx and original_idx < len(source):
            if source[original_idx].isspace():
                # Skip consecutive whitespace in source
                while original_idx < len(source) and source[original_idx].isspace():
                    original_idx += 1
            else:
                original_idx += 1
                norm_idx += 1
        return (original_idx, original_idx + len(text))

    return None


def _find_line_number(source: str, char_pos: int) -> int:
    """Find line number for a character position."""
    if char_pos <= 0:
        return 1
    return source[:char_pos].count("\n") + 1


def ground_extraction(
    extraction: Extraction,
    source_text: str,
    source_file: str = "",
) -> Extraction:
    """Add source grounding to an extraction.

    Finds the exact location of extraction_text in source_text.
    """
    if extraction.char_interval:
        # Already grounded
        if not extraction.source_file and source_file:
            extraction.source_file = source_file
            extraction.source_line = _find_line_number(source_text, extraction.char_interval[0])
        return extraction

    # Find location
    location = _find_text_location(source_text, extraction.extraction_text)
    if location:
        extraction.char_interval = location
        extraction.source_file = source_file
        extraction.source_line = _find_line_number(source_text, location[0])

        # Add context (surrounding text)
        start = max(0, location[0] - 50)
        end = min(len(source_text), location[1] + 50)
        extraction.source_context = source_text[start:end].replace("\n", " ")
    else:
        extraction.confidence *= 0.5  # Lower confidence if not grounded

    return extraction


def extract_from_code(
    source_text: str,
    source_file: str = "",
    extraction_classes: Optional[List[str]] = None,
) -> ExtractionResult:
    """Extract structured information from code using AST parsing.

    This is a non-LLM extraction that uses Python's AST module.

    Args:
        source_text: Source code text
        source_file: Source file path for grounding
        extraction_classes: Classes to extract (default: all)

    Returns:
        ExtractionResult with code structures
    """
    import ast

    if extraction_classes is None:
        extraction_classes = ["import", "function", "class", "decorator"]

    extractions: List[Extraction] = []

    try:
        tree = ast.parse(source_text)
    except SyntaxError as e:
        log.warning(f"Failed to parse {source_file}: {e}")
        return ExtractionResult(
            extractions=[],
            source_text=source_text,
            extraction_classes=extraction_classes,
            metadata={"error": str(e)},
        )

    # Extract imports
    if "import" in extraction_classes:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    ext = Extraction(
                        extraction_class="import",
                        extraction_text=f"import {alias.name}",
                        attributes={"module": alias.name, "type": "import"},
                    )
                    ext = ground_extraction(ext, source_text, source_file)
                    extractions.append(ext)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    ext = Extraction(
                        extraction_class="import",
                        extraction_text=f"from {module} import {alias.name}",
                        attributes={"module": module, "name": alias.name, "type": "from"},
                    )
                    ext = ground_extraction(ext, source_text, source_file)
                    extractions.append(ext)

    # Extract functions
    if "function" in extraction_classes:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                args = [arg.arg for arg in node.args.args]
                ext = Extraction(
                    extraction_class="function",
                    extraction_text=f"def {node.name}({', '.join(args)})",
                    attributes={
                        "name": node.name,
                        "args": args,
                        "line": node.lineno,
                        "is_method": False,
                    },
                )
                ext.source_file = source_file
                ext.source_line = node.lineno
                extractions.append(ext)

    # Extract classes
    if "class" in extraction_classes:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)

                # Get methods
                methods = []
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, ast.FunctionDef):
                        methods.append(item.name)

                ext = Extraction(
                    extraction_class="class",
                    extraction_text=f"class {node.name}",
                    attributes={
                        "name": node.name,
                        "bases": bases,
                        "methods": methods,
                        "line": node.lineno,
                    },
                )
                ext.source_file = source_file
                ext.source_line = node.lineno
                extractions.append(ext)

    return ExtractionResult(
        extractions=extractions,
        source_text=source_text,
        extraction_classes=extraction_classes,
        metadata={"method": "ast", "source_file": source_file},
    )


def extract_from_text(
    text: str,
    extraction_classes: List[str],
    examples: Optional[List[ExampleData]] = None,
    source_file: str = "",
) -> ExtractionResult:
    """Extract structured information from text using patterns.

    Non-LLM extraction using regex patterns.

    Args:
        text: Source text
        extraction_classes: Classes to extract
        examples: Optional examples (not used in pattern matching)
        source_file: Source file for grounding

    Returns:
        ExtractionResult
    """
    extractions: List[Extraction] = []

    # Pattern-based extraction
    patterns = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "url": r'https?://[^\s<>"{}|\\^`\[\]]+',
        "filepath": r"(?:^|\s)([a-zA-Z]:\\[^\s]+|/[^\s]+|[a-zA-Z0-9_./\\]+\.[a-zA-Z]+)",
        "function_call": r"(\w+)\(([^)]*)\)",
        "import": r"(?:from\s+([\w.]+)\s+)?import\s+([\w,\s]+)",
        "variable": r"(?:^|\n)\s*(\w+)\s*=",
    }

    for cls in extraction_classes:
        if cls in patterns:
            for match in re.finditer(patterns[cls], text):
                ext = Extraction(
                    extraction_class=cls,
                    extraction_text=match.group(0).strip(),
                    attributes={"pattern": cls},
                )
                ext = ground_extraction(ext, text, source_file)
                extractions.append(ext)

    return ExtractionResult(
        extractions=extractions,
        source_text=text,
        extraction_classes=extraction_classes,
        metadata={"method": "pattern", "source_file": source_file},
    )


def extract_with_examples(
    text: str,
    extraction_classes: List[str],
    examples: List[ExampleData],
    source_file: str = "",
) -> Tuple[str, List[Extraction]]:
    """Build prompt for LLM-based extraction with few-shot examples.

    This creates a prompt that can be sent to Jo's LLM for extraction.

    Args:
        text: Text to extract from
        extraction_classes: Classes to extract
        examples: Few-shot examples
        source_file: Source file for grounding

    Returns:
        Tuple of (prompt text, initial extractions from examples)
    """
    # Build prompt
    prompt_parts = [
        "## Extraction Task",
        "",
        f"Extract the following from the text: {', '.join(extraction_classes)}",
        "",
        "Rules:",
        "1. Extract ONLY information explicitly present in the text",
        "2. Use exact text for extractions (no paraphrasing)",
        "3. Provide attributes for context",
        "4. List extractions in order of appearance",
        "",
    ]

    # Add examples
    if examples:
        prompt_parts.append("## Examples")
        prompt_parts.append("")
        for i, example in enumerate(examples, 1):
            prompt_parts.append(f"### Example {i}")
            prompt_parts.append(example.to_prompt_format())
            prompt_parts.append("")

    # Add source text
    prompt_parts.extend(
        [
            "## Source Text",
            "",
            "```",
            text[:5000],  # Limit for LLM context
            "```",
            "",
            "## Extractions",
            "",
            "Provide extractions in JSON format:",
            "```json",
            "{",
            '  "extractions": [',
            "    {",
            '      "class": "extraction_class",',
            '      "text": "exact text from source",',
            '      "attributes": {"key": "value"}',
            "    }",
            "  ]",
            "}",
            "```",
        ]
    )

    return "\n".join(prompt_parts), []


def parse_llm_extraction(
    response: str,
    source_text: str,
    source_file: str = "",
) -> ExtractionResult:
    """Parse LLM extraction response into ExtractionResult.

    Args:
        response: LLM response text
        source_text: Original source text
        source_file: Source file for grounding

    Returns:
        ExtractionResult with grounded extractions
    """
    extractions: List[Extraction] = []

    # Try to find JSON in response
    json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            for ext_data in data.get("extractions", []):
                ext = Extraction(
                    extraction_class=ext_data.get("class", ""),
                    extraction_text=ext_data.get("text", ""),
                    attributes=ext_data.get("attributes", {}),
                )
                ext = ground_extraction(ext, source_text, source_file)
                extractions.append(ext)
        except json.JSONDecodeError:
            log.warning("Failed to parse LLM extraction JSON")

    # Extract classes used
    extraction_classes = list(set(e.extraction_class for e in extractions))

    return ExtractionResult(
        extractions=extractions,
        source_text=source_text,
        extraction_classes=extraction_classes,
        metadata={"method": "llm", "source_file": source_file},
    )


def export_to_vault(
    result: ExtractionResult,
    title: str = "Extraction Results",
    folder: str = "concepts",
    repo_dir: Optional[Path] = None,
) -> str:
    """Export extraction results to vault.

    Args:
        result: ExtractionResult to export
        title: Note title
        folder: Vault folder
        repo_dir: Repository directory

    Returns:
        Status message
    """
    if repo_dir is None:
        repo_dir = Path(os.environ.get("REPO_DIR", "."))

    vault_path = repo_dir / "vault" / folder / f"{title.lower().replace(' ', '_')}.md"

    try:
        vault_path.parent.mkdir(parents=True, exist_ok=True)
        vault_path.write_text(result.to_markdown(), encoding="utf-8")
        return f"Exported extraction results to vault ({len(result.extractions)} extractions)"
    except Exception as e:
        log.error(f"Failed to export to vault: {e}")
        return f"Export failed: {e}"
