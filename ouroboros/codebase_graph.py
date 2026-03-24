"""Codebase graph and ontology system.

This module provides tools for analyzing code structure, relationships,
and building an ontology system for task classification.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from networkx.readwrite.json_graph import node_link_data, node_link_graph

from ouroboros.memory import get_scratchpad
from ouroboros.tools import get_tool_registry
from ouroboros.utils import get_file_list

log = logging.getLogger(__name__)

# Global ontology tracker instance for relationship tracking
_ontology_tracker: Optional["OntologyTracker"] = None

def get_ontology_tracker() -> "OntologyTracker":
    """Get or create the global ontology tracker instance."""
    global _ontology_tracker
    if _ontology_tracker is None:
        _ontology_tracker = OntologyTracker()
    return _ontology_tracker