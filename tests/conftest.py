from __future__ import annotations

import sys
from pathlib import Path

# Make repository-root modules importable consistently across pytest launchers.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
