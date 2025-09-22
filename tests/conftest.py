"""Test configuration ensuring project package import resolution."""

import sys
from pathlib import Path

# Insert the project root into sys.path before any project imports.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
