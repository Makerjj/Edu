from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .api import OJApiError, OJClient
from .auth import AuthError, DingdangAuthClient
from .cli import _extract_student_code, _load_students, resolve_team
from .config import ensure_credentials, load_config
from .matcher import MatchError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="列出团队成员的 uid、username 和 nickname")
    parser.add_argument("--team", required=True, help="团队名称、gid 或团队链接")
    parser.add_argument(
        "--config",
        default="config.json",
        help="配置文件路径，默认读取当前目录下的 config.json",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="将团队学生名单保存为可编辑 JSON 文件",
    )
    return parser


def _student_json_payload(team, students) -> dict:
    return {
        "team_gid": team.group_id,
        "team_name": team.name,
        "students": [
            {
                "uid": student.uid,
                "username": student.username,
                "nickname": student.nickname,
                "real_name": student.nickname,
                "school": "",
                "phone": "",
            }
            for student in students
        ],
    }


def _write_students_json(path: Path, team, students) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_student_json_payload(team, students), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config_path = Path(args.config)
        config = load_config(config_path if config_path.exists() else None)
        config = ensure_credentials(config)

        auth_client = DingdangAuthClient()
        dingdang_token = auth_client.login(config.account or "", config.password or "")
        student_code = _extract_student_code(auth_client.get_students(dingdang_token))
        auth_session = auth_client.login_oj(dingdang_token, student_code)

        oj_client = OJClient(auth_session.oj_token)
        team = resolve_team(oj_client, args.team)
        students = _load_students(oj_client, team.group_id)

        print(f"团队: {team.name} (gid={team.group_id})")
        print("uid\tusername\tnickname")
        for student in students:
            print(f"{student.uid}\t{student.username}\t{student.nickname}")
        if args.output_json:
            output_path = Path(args.output_json)
            _write_students_json(output_path, team, students)
            print(f"已写入学生 JSON: {output_path}")
        return 0
    except (AuthError, OJApiError, MatchError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
