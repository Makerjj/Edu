import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.xdf_report.problem_lookup import main


if __name__ == "__main__":
    raise SystemExit(main())
