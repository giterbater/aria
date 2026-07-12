"""Conftest for tests — adds project root to sys.path."""

import sys
from pathlib import Path

# Add project root so that all top-level packages are importable
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
