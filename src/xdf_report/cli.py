from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import sys
from pathlib import Path

from pypinyin import lazy_pinyin

from .api import OJApiError, OJClient
from .auth import AuthError, DingdangAuthClient
from .config import ensure_credentials, load_config
from .excel_template import render_report
from .matcher import (
    MatchError,
    match_problem_queries,
    match_team_by_name,
    match_training_by_name,
    try_match_problem_query,
)
from .models import Problem, ReportRequest, Student, Team, Training
from .report_data import build_progress_rows

GROUP_SCAN_MAX_ID = 5000
GROUP_SCAN_WORKERS = 25


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="新东方学情反馈表生成工具")
    parser.add_argument("--team", required=True, help="团队名称，支持包含匹配")
    parser.add_argument("--training", required=True, help="训练名称，支持包含匹配")
    parser.add_argument(
        "--problems",
        required=True,
        help="题目名称或题号列表，使用英文逗号或中文逗号分隔",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="配置文件路径，默认读取当前目录下的 config.json",
    )
    parser.add_argument(
        "--after-class-problems",
        default=None,
        help="课后题名称或题号列表，使用英文逗号或中文逗号分隔；未匹配项会警告并跳过",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出目录或 .xlsx 文件路径，未提供时使用配置文件中的 output_dir",
    )
    parser.add_argument(
        "--students-json",
        default=None,
        help="显式指定学生列表 JSON 文件。仅当提供该参数时才使用该文件中的用户并按姓名排序。",
    )
    parser.add_argument(
        "--training-password",
        default=None,
        help="私有训练的训练密码；未提供时会在需要时提示输入",
    )
    return parser


def parse_problem_queries(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r"[，,]", raw) if item.strip()]


def _safe_filename(value: str) -> str:
    normalized = re.sub(r'[\\/:*?"<>|]+', "_", value).strip()
    return normalized or "未命名"


def build_output_path(request: ReportRequest) -> Path:
    problem_count = len(request.problem_queries)
    if problem_count <= 1:
        problem_part = request.problem_queries[0]
    else:
        problem_part = f"{request.problem_queries[0]}等{problem_count}题"
    filename = "_".join(
        [
            _safe_filename(request.team_name),
            _safe_filename(request.training_name),
            _safe_filename(problem_part),
            "学情反馈表.xlsx",
        ]
    )
    return request.output_dir / filename


def _resolve_output_target(output_arg: str | None, default_dir: Path) -> tuple[Path, Path | None]:
    if not output_arg:
        return default_dir, None

    target = Path(output_arg)
    if target.suffix.lower() == ".xlsx":
        return target.parent, target
    return target, None


def _require_template(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"模板文件不存在: {path}")


def _extract_student_code(students: list[dict]) -> str:
    for item in students:
        student_code = item.get("studentCode")
        if student_code:
            return str(student_code)
    raise AuthError("未从账号下获取到可用学生身份")


def _load_teams(client: OJClient, keyword: str) -> list[Team]:
    payload = client.get(
        "/get-group-list",
        {"currentPage": 1, "limit": 500, "keyword": keyword},
    )
    records = payload.get("data", {}).get("records", [])
    return [
        Team(group_id=int(record["id"]), name=str(record["name"]))
        for record in records
        if record.get("id") is not None and record.get("name")
    ]


def extract_group_id_from_query(query: str) -> int | None:
    raw = query.strip()
    if raw.isdigit():
        return int(raw)
    match = re.search(r"/group/(\d+)", raw)
    if match:
        return int(match.group(1))
    return None


def _load_team_by_id(client: OJClient, group_id: int) -> Team:
    payload = client.get("/get-group-detail", {"gid": group_id})
    if payload.get("status") not in (None, 200):
        raise MatchError(f"未找到团队 gid={group_id}")
    data = payload.get("data") or {}
    if not data.get("id") or not data.get("name"):
        raise MatchError(f"未找到团队 gid={group_id}")
    return Team(group_id=int(data["id"]), name=str(data["name"]))


def _team_is_accessible(client: OJClient, group_id: int) -> bool:
    try:
        client.get(
            "/group/get-training-list",
            {"currentPage": 1, "limit": 1, "gid": group_id},
        )
    except OJApiError:
        return False
    return True


def _scan_team_candidate(client: OJClient, group_id: int, query: str) -> Team | None:
    try:
        team = _load_team_by_id(client, group_id)
    except (OJApiError, MatchError):
        return None
    if query.lower() not in team.name.lower():
        return None
    if not _team_is_accessible(client, group_id):
        return None
    return team


def _scan_teams_by_name(
    client: OJClient,
    query: str,
    scan_max_id: int,
    scan_workers: int,
) -> list[Team]:
    matches: list[Team] = []
    with cf.ThreadPoolExecutor(max_workers=scan_workers) as executor:
        for team in executor.map(
            lambda gid: _scan_team_candidate(client, gid, query),
            range(1, scan_max_id + 1),
        ):
            if team is not None:
                matches.append(team)
    return matches


def resolve_team(
    client: OJClient,
    query: str,
    scan_max_id: int = GROUP_SCAN_MAX_ID,
    scan_workers: int = GROUP_SCAN_WORKERS,
) -> Team:
    group_id = extract_group_id_from_query(query)
    if group_id is not None:
        return _load_team_by_id(client, group_id)

    try:
        teams = _load_teams(client, query)
        return match_team_by_name(teams, query)
    except (OJApiError, MatchError):
        scanned_teams = _scan_teams_by_name(client, query, scan_max_id, scan_workers)
        if not scanned_teams:
            raise MatchError(
                f"未找到团队: {query}。已尝试官方列表接口和 gid 1-{scan_max_id} 的自动扫描。"
            )
        return match_team_by_name(scanned_teams, query)


def _load_trainings(client: OJClient, group_id: int) -> list[Training]:
    payload = client.get(
        "/group/get-training-list",
        {"currentPage": 1, "limit": 500, "gid": group_id},
    )
    records = payload.get("data", {}).get("records", [])
    return [
        Training(training_id=int(record["id"]), title=str(record["title"]))
        for record in records
        if record.get("id") is not None and record.get("title")
    ]


def _load_problems(client: OJClient, training_id: int) -> list[Problem]:
    payload = client.get("/get-training-problem-list", {"tid": training_id})
    records = payload.get("data", [])
    return [
        Problem(problem_id=str(record["problemId"]), title=str(record["title"]))
        for record in records
        if record.get("problemId") and record.get("title")
    ]


def _needs_training_registration(exc: OJApiError) -> bool:
    message = str(exc)
    return "该训练属于私有" in message or "'status': 401" in message


def _ensure_training_registered(
    client: OJClient,
    training_id: int,
    training_password: str | None,
) -> str:
    password = (training_password or "").strip() or input("训练密码: ").strip()
    if not password:
        raise MatchError("该训练需要训练密码")
    client.post("/register-training", {"tid": training_id, "password": password})
    return password


def load_problems_with_registration(
    client: OJClient,
    training_id: int,
    training_password: str | None,
) -> list[Problem]:
    try:
        return _load_problems(client, training_id)
    except OJApiError as exc:
        if not _needs_training_registration(exc):
            raise
    _ensure_training_registered(client, training_id, training_password)
    return _load_problems(client, training_id)


def find_training_index(trainings: list[Training], training: Training) -> int:
    for index, item in enumerate(trainings):
        if item.training_id == training.training_id:
            return index
    raise MatchError(f"未找到当前训练在列表中的位置: {training.title}")


def find_previous_training(
    trainings: list[Training], current_training: Training
) -> Training | None:
    current_index = find_training_index(trainings, current_training)
    if current_index == 0:
        return None
    return trainings[current_index - 1]


def _format_after_class_warning(
    query: str, current_error: str, previous_error: str | None
) -> str:
    parts = [f"课后题查询“{query}”已跳过", f"当前训练未匹配（{current_error}）"]
    if previous_error is None:
        parts.append("无上一训练")
    else:
        parts.append(f"上一训练未匹配（{previous_error}）")
    return "警告: " + "；".join(parts)


def resolve_after_class_problems(
    queries: list[str],
    current_problems: list[Problem],
    previous_problems: list[Problem] | None,
) -> tuple[list[Problem], bool, bool]:
    matched: list[Problem] = []
    matched_current = False
    matched_previous = False
    for query in queries:
        current_match = try_match_problem_query(current_problems, query)
        if isinstance(current_match, Problem):
            matched.append(current_match)
            matched_current = True
            continue

        if previous_problems is None:
            print(
                _format_after_class_warning(query, current_match, None),
                file=sys.stderr,
            )
            continue

        previous_match = try_match_problem_query(previous_problems, query)
        if isinstance(previous_match, Problem):
            matched.append(previous_match)
            matched_previous = True
            continue

        print(
            _format_after_class_warning(query, current_match, previous_match),
            file=sys.stderr,
        )
    return matched, matched_current, matched_previous


def _load_students(client: OJClient, group_id: int) -> list[Student]:
    payload = client.get(
        "/group/get-member-list",
        {"currentPage": 1, "limit": 500, "gid": group_id},
    )
    records = payload.get("data", {}).get("records", [])
    students: list[Student] = []
    for record in records:
        if record.get("auth") != 3:
            continue
        uid = record.get("uid")
        username = record.get("username")
        nickname = record.get("nickname") or username
        if not uid or not username or not nickname:
            continue
        students.append(
            Student(uid=str(uid), username=str(username), nickname=str(nickname))
        )
    return students


def _contains_chinese(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _student_name_sort_key(student: Student) -> tuple[int, tuple[str, ...], str]:
    name = (student.nickname or "").strip()
    if not name:
        return (2, tuple(), "")
    if _contains_chinese(name):
        return (0, tuple(lazy_pinyin(name)), name)
    return (1, (name.lower(),), name)


def _sort_students_by_name(students: list[Student]) -> list[Student]:
    return sorted(students, key=_student_name_sort_key)


def _load_students_from_json(path: Path) -> list[Student]:
    if not path.exists():
        raise FileNotFoundError(f"学生 JSON 文件不存在: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("students")
    if not isinstance(records, list):
        raise MatchError(f"学生 JSON 文件格式错误: {path}")

    students: list[Student] = []
    seen_uids: set[str] = set()
    for record in records:
        uid = record.get("uid")
        username = record.get("username")
        nickname = (
            record.get("real_name")
            or record.get("nickname")
            or username
        )
        if not uid or not username or not nickname:
            continue
        uid_key = str(uid)
        if uid_key in seen_uids:
            continue
        seen_uids.add(uid_key)
        students.append(
            Student(uid=uid_key, username=str(username), nickname=str(nickname))
        )

    return _sort_students_by_name(students)


def _load_rank_records(client: OJClient, training_id: int) -> list[dict]:
    payload = client.get(
        "/get-training-rank",
        {"currentPage": 1, "limit": 500, "tid": training_id},
    )
    return payload.get("data", {}).get("records", [])


def _merge_rank_records(*rank_record_groups: list[dict]) -> list[dict]:
    merged_by_uid: dict[str, dict] = {}
    for group in rank_record_groups:
        for record in group:
            uid = record.get("uid")
            if uid is None:
                continue
            uid_key = str(uid)
            submission_info = record.get("submissionInfo")
            normalized_submission_info = (
                dict(submission_info) if isinstance(submission_info, dict) else {}
            )
            existing = merged_by_uid.get(uid_key)
            if existing is None:
                merged_by_uid[uid_key] = {
                    **record,
                    "uid": uid_key,
                    "submissionInfo": normalized_submission_info,
                }
                continue

            existing_submission_info = existing.get("submissionInfo")
            if not isinstance(existing_submission_info, dict):
                existing_submission_info = {}
                existing["submissionInfo"] = existing_submission_info
            existing_submission_info.update(normalized_submission_info)
    return list(merged_by_uid.values())


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        problem_queries = parse_problem_queries(args.problems)
        after_class_queries = parse_problem_queries(args.after_class_problems or "")
        if not problem_queries:
            raise MatchError("请至少提供一个题目名称或题号")

        config_path = Path(args.config)
        config = load_config(config_path if config_path.exists() else None)
        config = ensure_credentials(config)
        _require_template(config.template_path)

        output_dir, explicit_output_path = _resolve_output_target(
            args.output, config.output_dir
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        auth_client = DingdangAuthClient()
        dingdang_token = auth_client.login(config.account or "", config.password or "")
        student_code = _extract_student_code(auth_client.get_students(dingdang_token))
        auth_session = auth_client.login_oj(dingdang_token, student_code)

        oj_client = OJClient(auth_session.oj_token)
        team = resolve_team(oj_client, args.team)

        trainings = _load_trainings(oj_client, team.group_id)
        training = match_training_by_name(trainings, args.training)

        problems = load_problems_with_registration(
            oj_client, training.training_id, args.training_password
        )
        matched_problems = match_problem_queries(problems, problem_queries)
        previous_training = find_previous_training(trainings, training)
        previous_problems: list[Problem] | None = None
        if after_class_queries and previous_training is not None:
            previous_problems = load_problems_with_registration(
                oj_client,
                previous_training.training_id,
                args.training_password,
            )
        (
            after_class_problems,
            matched_current_training,
            matched_previous_training,
        ) = resolve_after_class_problems(after_class_queries, problems, previous_problems)

        students_json_path: Path | None = (
            Path(args.students_json) if args.students_json else None
        )

        if students_json_path is not None:
            students = _load_students_from_json(students_json_path)
        else:
            students = _load_students(oj_client, team.group_id)
        students = _sort_students_by_name(students)

        rank_records = _load_rank_records(oj_client, training.training_id)
        after_class_rank_records: list[dict] = []
        if after_class_problems:
            if (
                matched_current_training
                and matched_previous_training
                and previous_training is not None
            ):
                previous_rank_records = _load_rank_records(
                    oj_client, previous_training.training_id
                )
                after_class_rank_records = _merge_rank_records(
                    rank_records, previous_rank_records
                )
            elif matched_previous_training and previous_training is not None:
                after_class_rank_records = _load_rank_records(
                    oj_client, previous_training.training_id
                )
            elif matched_current_training:
                after_class_rank_records = rank_records

        request = ReportRequest(
            team_name=team.name,
            training_name=training.title,
            problem_queries=[problem.title for problem in matched_problems],
            template_path=config.template_path,
            output_dir=output_dir,
            after_class_problem_queries=[
                problem.title for problem in after_class_problems
            ],
        )
        output_path = explicit_output_path or build_output_path(request)

        rows = build_progress_rows(
            students,
            matched_problems,
            rank_records,
            after_class_problems=after_class_problems,
            after_class_rank_records=after_class_rank_records,
        )
        render_report(
            request=request,
            problems=matched_problems,
            after_class_problems=after_class_problems,
            rows=rows,
            output_path=output_path,
        )
        print(output_path)
        return 0
    except (AuthError, OJApiError, MatchError, FileNotFoundError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
