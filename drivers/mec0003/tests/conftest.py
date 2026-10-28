# Makes `import mec0003` load drivers/mec0003/driver.py, no matter which
# directory pytest is run from.
import importlib.util
import sys
from pathlib import Path

_DRIVER = Path(__file__).resolve().parents[1] / "driver.py"
_spec = importlib.util.spec_from_file_location("mec0003", _DRIVER)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["mec0003"] = _mod
_spec.loader.exec_module(_mod)
