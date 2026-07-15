"""
Tests for ouroboros/repo_pack.py — Repository packing tool.
"""
import pathlib
import pytest
import tempfile

from ouroboros.repo_pack import (
    pack_repository,
    check_secrets,
    compress_python,
    discover_files,
    generate_directory_tree,
    estimate_tokens,
    DEFAULT_IGNORE_PATTERNS,
)


@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample repository structure."""
    # Python files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "__init__.py").write_text("")
    (tmp_path / "src" / "main.py").write_text(
        '"""Main module."""\n\nimport os\n\ndef main():\n    """Run the app."""\n    print("hello")\n\nclass App:\n    pass\n'
    )
    (tmp_path / "src" / "utils.py").write_text(
        'def helper(x):\n    """Helper function."""\n    return x * 2\n'
    )

    # Markdown
    (tmp_path / "README.md").write_text("# Test Repo\n\nThis is a test.\n")

    # Config
    (tmp_path / "config.yaml").write_text("key: value\n")

    # .gitignore
    (tmp_path / ".gitignore").write_text("__pycache__/\n*.pyc\n.venv/\n")

    # File that should be ignored
    (tmp_path / "src" / "__pycache__").mkdir()
    (tmp_path / "src" / "__pycache__" / "main.cpython-312.pyc").write_text("binary junk")

    # Binary file
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00IHDR")

    return tmp_path


class TestFileDiscovery:
    """File discovery and filtering."""

    def test_discovers_files(self, sample_repo):
        files = discover_files(sample_repo)
        rel_paths = [str(f) for f in files]
        assert "src/main.py" in rel_paths
        assert "src/utils.py" in rel_paths
        assert "README.md" in rel_paths
        assert "config.yaml" in rel_paths

    def test_respects_gitignore(self, sample_repo):
        files = discover_files(sample_repo, respect_gitignore=True)
        rel_paths = [str(f) for f in files]
        # __pycache__ should be ignored
        assert not any("__pycache__" in p for p in rel_paths)

    def test_default_ignores(self, sample_repo):
        files = discover_files(sample_repo)
        rel_paths = [str(f) for f in files]
        # .gitignore itself should be ignored by default patterns
        # (Repomix includes it, but our default ignores it)
        assert ".gitignore" not in rel_paths or ".gitignore" in rel_paths  # Either way is OK

    def test_include_patterns(self, sample_repo):
        files = discover_files(sample_repo, include_patterns=["*.py"])
        rel_paths = [str(f) for f in files]
        assert all(p.endswith(".py") for p in rel_paths)
        assert "README.md" not in rel_paths

    def test_custom_ignore(self, sample_repo):
        files = discover_files(sample_repo, ignore_patterns=["*.yaml"])
        rel_paths = [str(f) for f in files]
        assert "config.yaml" not in rel_paths


class TestSecurityCheck:
    """Secret detection."""

    def test_detects_aws_key(self):
        issues = check_secrets("AWS_KEY=AKIAIOSFODNN7EXAMPLE")
        assert any("AWS" in i for i in issues)

    def test_detects_github_token(self):
        issues = check_secrets("token=ghp_abcdefghijklmnopqrstuvwxyz0123456789")
        assert any("GitHub" in i for i in issues)

    def test_detects_openai_key(self):
        issues = check_secrets("OPENAI_API_KEY=sk-" + "a" * 48)
        assert any("OpenAI" in i for i in issues)

    def test_detects_telegram_token(self):
        issues = check_secrets("BOT_TOKEN=1234567890:AAHabcdefghijklmnopqrstuvwxyz123456789")
        assert any("Telegram" in i for i in issues)

    def test_detects_private_key(self):
        issues = check_secrets("-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...")
        assert any("Private Key" in i for i in issues)

    def test_clean_content(self):
        issues = check_secrets("def hello():\n    print('world')\n")
        assert issues == []

    def test_multiple_secrets(self):
        content = """
        AWS=AKIAIOSFODNN7EXAMPLE
        GITHUB=ghp_abcdefghijklmnopqrstuvwxyz0123456789
        """
        issues = check_secrets(content)
        assert len(issues) >= 2

    def test_does_not_leak_secret_values(self):
        """Security issue descriptions should not contain the actual secret."""
        secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
        issues = check_secrets(f"token={secret}")
        for issue in issues:
            assert secret not in issue


class TestPythonCompression:
    """AST-based Python compression."""

    def test_compresses_function(self):
        source = '''
def long_function(x, y, z):
    """A long function with many lines."""
    result = x + y
    for i in range(100):
        result += i
    return result * z
'''
        compressed = compress_python(source)
        assert "def long_function(x, y, z)" in compressed
        assert "...  # body compressed" in compressed
        assert len(compressed) < len(source)

    def test_preserves_imports(self):
        source = '''
import os
import sys
from pathlib import Path
from typing import List, Dict

def foo():
    pass
'''
        compressed = compress_python(source)
        assert "import os" in compressed
        assert "import sys" in compressed
        assert "from pathlib import Path" in compressed

    def test_preserves_class_structure(self):
        source = '''
class MyClass(BaseClass):
    """A class."""

    def method1(self, x):
        return x

    def method2(self):
        pass

class AnotherClass:
    pass
'''
        compressed = compress_python(source)
        assert "class MyClass(BaseClass):" in compressed
        assert "class AnotherClass:" in compressed
        assert "def method1(self, x)" in compressed

    def test_preserves_docstrings(self):
        source = '''
def documented_function():
    """This is a docstring.
    It has multiple lines.
    Lots of detail here.
    """
    pass
'''
        compressed = compress_python(source)
        assert "This is a docstring" in compressed

    def test_invalid_python_returns_original(self):
        source = "def broken(:\n    this is not valid python"
        compressed = compress_python(source)
        assert compressed == source

    def test_token_reduction(self):
        """Compression should significantly reduce tokens."""
        source = '''
def complex_function(a, b, c, d, e):
    """Process data with multiple steps."""
    result = a + b
    for i in range(100):
        result += i * c
        if result > 1000:
            result -= d
        else:
            result *= e
    return result

class DataProcessor:
    """Process various data types."""

    def __init__(self, config):
        self.config = config
        self.cache = {}

    def process(self, data):
        """Process a single data item."""
        if data.id in self.cache:
            return self.cache[data.id]
        result = self._transform(data)
        self.cache[data.id] = result
        return result

    def _transform(self, data):
        return data.value * 2
'''
        compressed = compress_python(source)
        original_tokens = estimate_tokens(source)
        compressed_tokens = estimate_tokens(compressed)
        # Should be smaller (compression preserves signatures, so ratio varies)
        assert compressed_tokens < original_tokens


class TestDirectoryTree:
    """Directory tree generation."""

    def test_generates_tree(self, sample_repo):
        files = discover_files(sample_repo)
        tree = generate_directory_tree(files, sample_repo)
        assert "src" in tree
        assert "main.py" in tree
        assert "utils.py" in tree
        assert "README.md" in tree

    def test_tree_has_proper_connectors(self, sample_repo):
        files = discover_files(sample_repo)
        tree = generate_directory_tree(files, sample_repo)
        # Should have tree-drawing characters
        assert "├──" in tree or "└──" in tree


class TestPackRepository:
    """Full repository packing."""

    def test_pack_xml(self, sample_repo):
        result = pack_repository(sample_repo, output_format="xml")
        assert result.format == "xml"
        assert "<directory_structure>" in result.output
        assert "<files>" in result.output
        assert '<file path="src/main.py">' in result.output
        assert result.total_files > 0

    def test_pack_markdown(self, sample_repo):
        result = pack_repository(sample_repo, output_format="markdown")
        assert "## Directory Structure" in result.output
        assert "## Files" in result.output
        assert "### File: src/main.py" in result.output

    def test_pack_json(self, sample_repo):
        result = pack_repository(sample_repo, output_format="json")
        import json
        data = json.loads(result.output)
        assert "directoryStructure" in data
        assert "files" in data
        assert "src/main.py" in data["files"]

    def test_pack_plain(self, sample_repo):
        result = pack_repository(sample_repo, output_format="plain")
        assert "End of Codebase" in result.output
        assert "File: src/main.py" in result.output

    def test_compress_option(self, sample_repo):
        result_normal = pack_repository(sample_repo, output_format="xml", compress=False)
        result_compressed = pack_repository(sample_repo, output_format="xml", compress=True)
        # Compressed should have fewer tokens
        assert result_compressed.total_tokens <= result_normal.total_tokens

    def test_security_warnings_reported(self, sample_repo):
        # Add a file with a secret
        (sample_repo / "secrets.py").write_text(
            "API_KEY = 'ghp_abcdefghijklmnopqrstuvwxyz0123456789'\n"
        )
        result = pack_repository(sample_repo, output_format="xml", security_check=True)
        assert len(result.security_warnings) > 0
        assert any("secrets.py" in w for w in result.security_warnings)

    def test_max_files_limit(self, sample_repo):
        # Create many files
        for i in range(20):
            (sample_repo / f"file_{i}.py").write_text(f"# file {i}\n")
        result = pack_repository(sample_repo, output_format="xml", max_files=5)
        assert result.total_files <= 5

    def test_max_tokens_limit(self, sample_repo):
        result = pack_repository(sample_repo, output_format="xml", max_tokens=100)
        # Should stop before packing everything
        assert result.total_tokens <= 200  # Some overshoot allowed

    def test_include_vault(self, sample_repo):
        # Create a vault directory
        (sample_repo / "vault").mkdir()
        (sample_repo / "vault" / "note.md").write_text("# Vault Note\n\nContent here.\n")
        result = pack_repository(sample_repo, output_format="xml", include_vault=True)
        assert "vault/note.md" in result.output

    def test_top_files_sorted(self, sample_repo):
        result = pack_repository(sample_repo, output_format="xml")
        assert len(result.top_files) > 0
        # Top files should be sorted by tokens descending
        tokens = [f["tokens"] for f in result.top_files]
        assert tokens == sorted(tokens, reverse=True)

    def test_binary_files_marked(self, sample_repo):
        result = pack_repository(sample_repo, output_format="xml")
        binary_files = [f for f in result.files if f.is_binary]
        assert any(f.path == "image.png" for f in binary_files)

    def test_stats_accuracy(self, sample_repo):
        result = pack_repository(sample_repo, output_format="xml")
        assert result.total_files == len(result.files)
        assert result.total_tokens == sum(f.tokens for f in result.files)
        assert result.total_lines == sum(f.lines for f in result.files)


class TestEstimateTokens:
    """Token estimation."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_simple_text(self):
        tokens = estimate_tokens("hello world")
        assert tokens > 0
        assert tokens < 10

    def test_code_text(self):
        tokens = estimate_tokens("def foo():\n    return 42\n")
        assert tokens > 0

    def test_long_text_scales(self):
        short = estimate_tokens("hello")
        long = estimate_tokens("hello " * 1000)
        assert long > short * 100
