"""Placeholder full-suite entrypoint delegating to minimal first validation."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.run_minimal_validation import main


if __name__ == "__main__":
    main()
