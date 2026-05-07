#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

# exec "$PYTHON_BIN" "$ROOT_DIR/xdf_report.py" \
#   --team "易生活102 C1" \
#   --training "字符羊肉串" \
#   --problems "字符串统计, 神秘咒语, 石头剪刀布" \
#   --students-json "$ROOT_DIR/students.6-4.json" \
#   --after-class-problems "校门外的树, GESP 二级]自幂数判断" \
#   --training-password 1 \
#   --output "$ROOT_DIR/after_class"

# exec "$PYTHON_BIN" "$ROOT_DIR/xdf_report.py" \
#   --team "信奥C++线上329班" \
#   --training "结构体与排序" \
#   --problems "结构体排序, 生日" \
#   --students-json "$ROOT_DIR/students.6-3.json" \
#   --training-password 1 \
#   --output "$ROOT_DIR/after_class"

  exec "$PYTHON_BIN" "$ROOT_DIR/xdf_report.py" \
  --team "易生活102 C1" \
  --training "数组与循环结构" \
  --problems "停放卡车,小杨的智慧购物,小球颜色数" \
  --after-class-problems "图书馆" \
  --students-json "$ROOT_DIR/students.6-1.json" \
  --training-password 1 \
  --output "$ROOT_DIR/after_class"

#信奥C++线上329班
#凤凰205-C++
#易生活102 C1
