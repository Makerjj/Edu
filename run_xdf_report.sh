#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

TEAM="${1:-${XDF_TEAM:-易生活102 C1}}"
TRAINING="${2:-${XDF_TRAINING:-二分查找}}"
PROBLEMS="${3:-${XDF_PROBLEMS:-找苹果,字典找字,查找}}"
TRAINING_PASSWORD="${4:-${XDF_TRAINING_PASSWORD:-1}}"
STUDENTS_JSON="${5:-${XDF_STUDENTS_JSON:-}}"
AFTER_CLASS_PROBLEMS="${6:-${XDF_AFTER_CLASS_PROBLEMS:-}}"

CONFIG_PATH="${XDF_CONFIG:-$ROOT_DIR/config.json}"
OUTPUT_PATH="${XDF_OUTPUT:-}"

if [[ "${TEAM}" == "-h" || "${TEAM}" == "--help" ]]; then
  cat <<'EOF'
用法:
  ./run_xdf_report.sh
  ./run_xdf_report.sh "团队名称" "训练名称" "题目1,题目2,题目3" "训练密码" "./students.c1-3.json" "课后题1,课后题2"

可选环境变量:
  XDF_CONFIG             配置文件路径，默认 ./config.json
  XDF_OUTPUT             输出目录或 .xlsx 文件路径
  XDF_TEAM               团队名称
  XDF_TRAINING           训练名称
  XDF_PROBLEMS           题目列表，逗号分隔
  XDF_TRAINING_PASSWORD  训练密码
  XDF_STUDENTS_JSON      学生列表 JSON 文件路径
  XDF_AFTER_CLASS_PROBLEMS  课后题列表，逗号分隔
EOF
  exit 0
fi

ARGS=(
  "$ROOT_DIR/xdf_report.py"
  "--team" "$TEAM"
  "--training" "$TRAINING"
  "--problems" "$PROBLEMS"
)

if [[ -n "$TRAINING_PASSWORD" ]]; then
  ARGS+=("--training-password" "$TRAINING_PASSWORD")
fi

if [[ -n "$STUDENTS_JSON" ]]; then
  ARGS+=("--students-json" "$STUDENTS_JSON")
fi

if [[ -n "$AFTER_CLASS_PROBLEMS" ]]; then
  ARGS+=("--after-class-problems" "$AFTER_CLASS_PROBLEMS")
fi

if [[ -f "$CONFIG_PATH" ]]; then
  ARGS+=("--config" "$CONFIG_PATH")
fi

if [[ -n "$OUTPUT_PATH" ]]; then
  ARGS+=("--output" "$OUTPUT_PATH")
fi

exec "$PYTHON_BIN" "${ARGS[@]}"
