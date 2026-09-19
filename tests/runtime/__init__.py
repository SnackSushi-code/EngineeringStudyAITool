from pathlib import Path
import sys

RUNTIME_SRC = Path(__file__).resolve().parents[2] / "services" / "runtime" / "src"
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))
