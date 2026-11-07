"""Double-click launcher (no console window). Use start.bat the first time."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evnia_ambiglow.app import main  # noqa: E402

main()
