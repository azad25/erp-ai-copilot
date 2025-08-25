"""Test configuration for pytest.

This module sets up the Python path for tests and provides fixtures.
"""

import os
import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))