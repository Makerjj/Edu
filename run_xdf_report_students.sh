#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

TEAM="${1:-易生活102 C1}"
TRAINING="${2:-二分查找}"
PROBLEMS="${3:-找苹果,字典找字,查找}"
STUDENTS_JSON="${4:-$ROOT_DIR/students.c1-3.json}"
AFTER_CLASS_PROBLEMS="${5:-${XDF_AFTER_CLASS_PROBLEMS:-}}"

ARGS=(
  "$ROOT_DIR/xdf_report.py"
  "--team" "$TEAM"
  "--training" "$TRAINING"
  "--problems" "$PROBLEMS"
  "--students-json" "$STUDENTS_JSON"
)

if [[ -n "$AFTER_CLASS_PROBLEMS" ]]; then
  ARGS+=("--after-class-problems" "$AFTER_CLASS_PROBLEMS")
fi

exec "$PYTHON_BIN" "${ARGS[@]}"
#./run_xdf_report_students.sh "易生活102 C1" "二分查找" "找苹果,字典找字,查找" "./students.c1-3.json" "验证密码,逢7过"
