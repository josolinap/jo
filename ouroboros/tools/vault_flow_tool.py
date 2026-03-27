"""Vault Flow Tools - Tools for incremental indexing of vault notes using CocoIndex.

Registers the following as tools Jo can use:
- vault_incremental_index: Index vault notes into a LanceDB vector store using CocoIndex incremental flows
- vault_search_semantic: Search indexed vault notes using semantic similarity
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Optional CocoIndex import
try:
    import cocoindex
    from cocoindex import FlowBuilder, DataScope

    _COCOINDEX_AVAILABLE = True
except Exception:  # ImportError or runtime error
    cocoindex = None  # type: ignore
    FlowBuilder = None  # type: ignore
    DataScope = None  # type: ignore
    _COCOINDEX_AVAILABLE = False
    log.debug("CocoIndex not available; vault flow tools will be disabled. Install with: pip install cocoindex")

# Optional LanceDB import (for vector storage)
try:
    import lancedb

    _LANCEDB_AVAILABLE = True
except Exception:
    lancedb = None  # type: ignore
    _LANCEDB_AVAILABLE = False
    log.debug("LanceDB not available; falling back to JSON storage for embeddings. Install with: pip install lancedb")


def _vault_incremental_index(
    ctx: ToolContext,
    full_reindex: bool = False,
) -> str:
    """Run an incremental CocoIndex flow to index vault notes into a vector store.

    Args:
        full_reindex: If True, delete existing index and rebuild from scratch (default False)

    Returns:
        JSON string with indexing results or error message
    """
    if not _COCOINDEX_AVAILABLE or not _LANCEDB_AVAILABLE:
        # Fallback to simple TF-IDF indexing (no external dependencies)
        from ouroboros.tools.embedding_simple import _vault_index_simple

        return _vault_index_simple(ctx, full_reindex)

    try:
        # Determine paths
        vault_dir = ctx.repo_path("vault")
        if not vault_dir.exists():
            return json.dumps({"error": "Vault directory not found", "indexed": 0})

        # Define storage location for LanceDB
        lancedb_path = ctx.drive_path("state") / "vault_vectors.lancedb"
        lancedb_path.parent.mkdir(parents=True, exist_ok=True)

        # Connect to LanceDB
        db = lancedb.connect(str(lancedb_path))

        # Define table name
        table_name = "vault_notes"

        # Create or open table
        if full_reindex:
            try:
                db.drop_table(table_name)
            except Exception:
                pass  # Ignore if table doesn't exist

        # Try to open existing table, otherwise create
        try:
            table = db.open_table(table_name)
            table_exists = True
        except Exception:
            table_exists = False

        # Define the CocoIndex flow
        def vault_flow(flow_builder: FlowBuilder, data_scope: DataScope) -> None:
            # Add vault notes as source
            data_scope["notes"] = flow_builder.add_source(
                cocoindex.sources.LocalFile(
                    path=str(vault_dir),
                    file_pattern="**/*.md",
                    # Optional: exclude certain directories if needed
                )
            )

            # Add collector for the vector store
            vectors = data_scope.add_collector()

            # Process each note
            with data_scope["notes"].row() as note:
                # Read the file content
                note["content"] = note["path"].read_text(encoding="utf-8")
                # Extract filename (relative to vault)
                note["filename"] = pathlib.Path(note["path"]).name
                note["relative_path"] = str(pathlib.Path(note["path"]).relative_to(vault_dir))

                # Generate embedding
                note["embedding"] = note["content"].transform(
                    cocoindex.functions.SentenceTransformerEmbed(model="sentence-transformers/all-MiniLM-L6-v2")
                )

                # Collect into LanceDB
                vectors.collect(
                    filename=note["filename"],
                    relative_path=note["relative_path"],
                    content=note["content"],
                    embedding=note["embedding"],
                )

            # Export to LanceDB table
            vectors.export(
                table_name,
                cocoindex.targets.LanceDB(uri=str(lancedb_path)),
                # Primary key could be a hash of the path, but we'll let LanceDB handle it
                # We'll store the relative_path as a field for retrieval
            )

        # Run the flow
        if full_reindex:
            log.info("Starting full reindex of vault notes")
        else:
            log.info("Starting incremental indexing of vault notes")

        # CocoIndex flow execution
        cocoindex.run_flow(vault_flow)

        # Get count of vectors in table
        if table_exists and not full_reindex:
            # For incremental, we could compute delta, but for simplicity we'll just report total
            pass

        try:
            tbl = db.open_table(table_name)
            count = tbl.count_rows()
        except Exception:
            count = 0

        return json.dumps(
            {
                "indexed": count,
                "table": table_name,
                "location": str(lancedb_path),
                "full_reindex": full_reindex,
                "status": "success",
            }
        )

    except Exception as e:
        log.error(f"Vault indexing failed: {e}")
        return json.dumps({"error": f"Vault indexing failed: {str(e)}", "indexed": 0})


def _vault_search_semantic(
    ctx: ToolContext,
    query: str,
    top_k: int = 5,
) -> str:
    """Search vault notes using semantic similarity via the LanceDB index.

    Args:
        query: Search query text
        top_k: Number of results to return (default 5)

    Returns:
        JSON string with search results
    """
    if not query or not query.strip():
        return json.dumps({"error": "Empty query provided", "results": []})

    if not _COCOINDEX_AVAILABLE or not _LANCEDB_AVAILABLE:
        # Fallback to simple TF-IDF search (no external dependencies)
        from ouroboros.tools.embedding_simple import _vault_search_simple

        return _vault_search_simple(ctx, query, top_k)

    try:
        # Connect to the LanceDB table
        lancedb_path = ctx.drive_path("state") / "vault_vectors.lancedb"
        if not lancedb_path.exists():
            return json.dumps(
                {"error": "Vault vector index not found. Run vault_incremental_index first.", "results": []}
            )

        db = lancedb.connect(str(lancedb_path))
        try:
            table = db.open_table("vault_notes")
        except Exception:
            return json.dumps(
                {"error": "Vault notes table not found. Run vault_incremental_index first.", "results": []}
            )

        # Generate embedding for the query
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("all-MiniLM-L6-v2")
            query_embedding = model.encode(query.strip())
            query_list = [float(x) for x in query_embedding]
        except Exception as e:
            return json.dumps({"error": f"Failed to embed query: {str(e)}", "results": []})

        # Search using LanceDB's vector search
        # LanceDB's search returns a LanceTable with _distance and _score etc.
        results = table.search(query_list).limit(top_k).to_pandas()

        # Format results
        formatted_results = []
        for _, row in results.iterrows():
            formatted_results.append(
                {
                    "filename": row.get("filename", ""),
                    "relative_path": row.get("relative_path", ""),
                    "content_preview": row.get("content", "")[:200]
                    + ("..." if len(row.get("content", "")) > 200 else ""),
                    "similarity": float(row.get("_distance", 0.0)),  # LanceDB returns distance; lower is better
                    # Note: LanceDB's distance is Euclidean by default; we could convert to similarity if needed
                    # For simplicity, we'll just return the distance and note that lower is better.
                    # Alternatively, we could compute cosine similarity if we stored normalized vectors.
                    "path": row.get("relative_path", ""),
                }
            )

        # Sort by similarity (ascending distance = higher similarity)
        formatted_results.sort(key=lambda x: x["similarity"])

        return json.dumps(
            {
                "query": query[:100] + ("..." if len(query) > 100 else ""),
                "results_count": len(formatted_results),
                "results": formatted_results,
            }
        )

    except Exception as e:
        log.error(f"Vault semantic search failed: {e}")
        return json.dumps({"error": f"Vault semantic search failed: {str(e)}", "results": []})
