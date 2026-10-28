# Core tests: makes `import guardian` load core/guardian/guardian.py.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core" / "guardian"))
