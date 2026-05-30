from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _prepare_script_sandbox(tmp_path: Path, script_name: str) -> tuple[Path, Path]:
    project_root = Path.cwd()
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()

    script_path = sandbox_root / script_name
    shutil.copy(project_root / script_name, script_path)
    script_path.chmod(0o755)

    python_bin = sandbox_root / ".venv" / "bin" / "python"
    python_bin.parent.mkdir(parents=True)
    capture_path = sandbox_root / "captured_args.txt"
    python_bin.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s\n' \"$@\" > \"" + str(capture_path) + "\"\n",
        encoding="utf-8",
    )
    python_bin.chmod(0o755)

    (sandbox_root / "xdf_report.py").write_text("placeholder\n", encoding="utf-8")
    (sandbox_root / "config.json").write_text("{}", encoding="utf-8")
    return script_path, capture_path


def test_run_xdf_report_forwards_after_class_problems_and_students_json(tmp_path: Path) -> None:
    script_path, capture_path = _prepare_script_sandbox(tmp_path, "run_xdf_report.sh")

    subprocess.run(
        [
            str(script_path),
            "信奥C++线上329班",
            "二分查找",
            "找苹果,字典找字",
            "1",
            "./students.online-329.json",
            "验证密码,逢7过",
        ],
        check=True,
        cwd=script_path.parent,
        env={**os.environ, "PATH": os.environ["PATH"]},
    )

    forwarded_args = capture_path.read_text(encoding="utf-8").splitlines()
    assert forwarded_args == [
        str(script_path.parent / "xdf_report.py"),
        "--team",
        "信奥C++线上329班",
        "--training",
        "二分查找",
        "--problems",
        "找苹果,字典找字",
        "--training-password",
        "1",
        "--students-json",
        "./students.online-329.json",
        "--after-class-problems",
        "验证密码,逢7过",
        "--config",
        str(script_path.parent / "config.json"),
    ]


def test_run_xdf_report_students_forwards_after_class_problems(tmp_path: Path) -> None:
    script_path, capture_path = _prepare_script_sandbox(tmp_path, "run_xdf_report_students.sh")

    subprocess.run(
        [
            str(script_path),
            "信奥C++线上329班",
            "二分查找",
            "找苹果,字典找字",
            "./students.online-329.json",
            "验证密码,逢7过",
        ],
        check=True,
        cwd=script_path.parent,
        env={**os.environ, "PATH": os.environ["PATH"]},
    )

    forwarded_args = capture_path.read_text(encoding="utf-8").splitlines()
    assert forwarded_args == [
        str(script_path.parent / "xdf_report.py"),
        "--team",
        "信奥C++线上329班",
        "--training",
        "二分查找",
        "--problems",
        "找苹果,字典找字",
        "--students-json",
        "./students.online-329.json",
        "--after-class-problems",
        "验证密码,逢7过",
    ]


def test_run_sh_is_a_directly_executable_wrapper(tmp_path: Path) -> None:
    script_path, capture_path = _prepare_script_sandbox(tmp_path, "run.sh")

    subprocess.run(
        [str(script_path)],
        check=True,
        cwd=tmp_path,
        env={**os.environ, "PATH": os.environ["PATH"]},
    )

    forwarded_args = capture_path.read_text(encoding="utf-8").splitlines()
    assert forwarded_args == [
        str(script_path.parent / "xdf_report.py"),
        "--team",
        "易生活102 C1",
        "--training",
        "数组与循环结构",
        "--problems",
        "停放卡车,小杨的智慧购物,小球颜色数",
        "--after-class-problems",
        "图书馆",
        "--students-json",
        str(script_path.parent / "students.6-1.json"),
        "--training-password",
        "1",
        "--output",
        str(script_path.parent / "after_class"),
    ]
