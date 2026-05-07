from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.xdf_report.api import OJApiError, OJClient
from src.xdf_report.auth import AuthError, DingdangAuthClient
from src.xdf_report.cli import (
    _extract_student_code,
    _load_rank_records,
    _load_students_from_json,
    _load_students,
    _load_problems,
    _load_trainings,
    _merge_rank_records,
    _sort_students_by_name,
    build_output_path,
    _ensure_training_registered,
    find_previous_training,
    _needs_training_registration,
    _scan_teams_by_name,
)
from src.xdf_report.config import ensure_credentials, load_config
from src.xdf_report.excel_template import render_report
from src.xdf_report.matcher import MatchError
from src.xdf_report.models import Problem, ReportRequest, Team, Training
from src.xdf_report.report_data import build_progress_rows


class AppState:
    client: OJClient | None = None
    config = None
    teams: list[dict] | None = None
    trainings_by_team: dict[int, list[dict]] = {}
    students_by_team: dict[int, list[dict]] = {}
    problems_by_training: dict[tuple[int, str], list[dict]] = {}
    downloads: dict[str, Path] = {}


state = AppState()


def get_config():
    if state.config is None:
        state.config = ensure_credentials(load_config(PROJECT_ROOT / "config.json"))
    return state.config


def get_client() -> OJClient:
    if state.client is not None:
        return state.client

    config = get_config()
    auth_client = DingdangAuthClient()
    dingdang_token = auth_client.login(config.account or "", config.password or "")
    student_code = _extract_student_code(auth_client.get_students(dingdang_token))
    auth_session = auth_client.login_oj(dingdang_token, student_code)
    state.client = OJClient(auth_session.oj_token)
    return state.client


def list_teams() -> list[dict]:
    if state.teams is not None:
        return state.teams

    teams = _scan_teams_by_name(get_client(), "", 5000, 25)
    state.teams = [
        {"groupId": team.group_id, "name": team.name}
        for team in sorted(teams, key=lambda item: item.group_id)
    ]
    return state.teams


def list_trainings(group_id: int) -> list[dict]:
    if group_id not in state.trainings_by_team:
        trainings = _load_trainings(get_client(), group_id)
        state.trainings_by_team[group_id] = [
            {"trainingId": training.training_id, "title": training.title}
            for training in trainings
        ]
    return state.trainings_by_team[group_id]


def list_students(group_id: int) -> list[dict]:
    if group_id not in state.students_by_team:
        students = _sort_students_by_name(_load_students(get_client(), group_id))
        state.students_by_team[group_id] = [
            {
                "uid": student.uid,
                "username": student.username,
                "nickname": student.nickname,
                "realName": student.nickname,
            }
            for student in students
        ]
    return state.students_by_team[group_id]


def list_problems(training_id: int, training_password: str) -> list[dict]:
    cache_key = (training_id, training_password)
    if cache_key in state.problems_by_training:
        return state.problems_by_training[cache_key]

    client = get_client()
    try:
        problems = _load_problems(client, training_id)
    except OJApiError as exc:
        if not _needs_training_registration(exc):
            raise
        if not training_password:
            raise PermissionError("该训练属于私有训练，请先填写训练密码") from exc
        _ensure_training_registered(client, training_id, training_password)
        problems = _load_problems(client, training_id)

    state.problems_by_training[cache_key] = [
        {"problemId": problem.problem_id, "title": problem.title}
        for problem in problems
    ]
    return state.problems_by_training[cache_key]


def list_problem_choices(
    group_id: int,
    training_id: int,
    training_password: str,
    include_previous: bool,
) -> list[dict]:
    choices = [
        {**problem, "source": problem.get("source", "current")}
        for problem in list_problems(training_id, training_password)
    ]
    if not include_previous:
        return choices

    trainings = _load_trainings(get_client(), group_id)
    current_training = next(
        (training for training in trainings if training.training_id == training_id),
        None,
    )
    if current_training is None:
        return choices
    previous_training = find_previous_training(trainings, current_training)
    if previous_training is None:
        return choices

    try:
        previous_problems = list_problems(
            previous_training.training_id, training_password
        )
    except PermissionError:
        previous_problems = []
    choices.extend(
        {
            **problem,
            "source": "previous",
            "trainingId": previous_training.training_id,
            "trainingTitle": previous_training.title,
        }
        for problem in previous_problems
    )
    return choices


def _problem_from_payload(payload: dict) -> Problem:
    return Problem(problem_id=str(payload["problemId"]), title=str(payload["title"]))


def _find_team(group_id: int) -> Team:
    for team in list_teams():
        if int(team["groupId"]) == group_id:
            return Team(group_id=group_id, name=str(team["name"]))
    raise MatchError(f"未找到团队 gid={group_id}")


def _find_training(group_id: int, training_id: int) -> Training:
    for training in list_trainings(group_id):
        if int(training["trainingId"]) == training_id:
            return Training(training_id=training_id, title=str(training["title"]))
    raise MatchError(f"未找到训练 tid={training_id}")


def generate_report(payload: dict) -> dict:
    group_id = int(payload.get("teamId") or payload.get("team") or 0)
    training_id = int(payload.get("trainingId") or payload.get("training") or 0)
    training_password = str(payload.get("trainingPassword") or "").strip()
    students_json = str(payload.get("studentsJson") or "").strip()
    problem_titles = [
        str(value).strip()
        for value in payload.get("problems", [])
        if str(value).strip()
    ]
    after_class_titles = [
        str(value).strip()
        for value in payload.get("afterClassProblems", [])
        if str(value).strip()
    ]
    if not group_id:
        raise MatchError("请选择团队")
    if not training_id:
        raise MatchError("请选择训练")
    if not problem_titles:
        raise MatchError("请至少选择一道课堂题目")

    config = get_config()
    if not config.template_path.exists():
        raise FileNotFoundError(f"模板文件不存在: {config.template_path}")

    client = get_client()
    team = _find_team(group_id)
    training = _find_training(group_id, training_id)
    current_problem_payloads = list_problems(training_id, training_password)
    current_problems = [_problem_from_payload(item) for item in current_problem_payloads]
    selected_problems = [
        problem for problem in current_problems if problem.title in set(problem_titles)
    ]
    if len(selected_problems) != len(set(problem_titles)):
        raise MatchError("部分课堂题目不在当前训练中，请重新选择")

    trainings = [
        Training(training_id=int(item["trainingId"]), title=str(item["title"]))
        for item in list_trainings(group_id)
    ]
    previous_training = find_previous_training(trainings, training)
    previous_problem_payloads: list[dict] = []
    if previous_training is not None:
        try:
            previous_problem_payloads = list_problems(
                previous_training.training_id, training_password
            )
        except PermissionError:
            previous_problem_payloads = []
    after_lookup = {
        item["title"]: _problem_from_payload(item)
        for item in [*current_problem_payloads, *previous_problem_payloads]
    }
    after_class_problems = [
        after_lookup[title] for title in after_class_titles if title in after_lookup
    ]

    if students_json:
        students_path = Path(students_json)
        if not students_path.is_absolute():
            students_path = PROJECT_ROOT / students_path
        students = _load_students_from_json(students_path)
    else:
        students = _sort_students_by_name(_load_students(client, group_id))
    rank_records = _load_rank_records(client, training_id)
    after_class_rank_records: list[dict] = []
    has_current_after = any(problem.title in set(after_class_titles) for problem in current_problems)
    has_previous_after = any(
        item["title"] in set(after_class_titles) for item in previous_problem_payloads
    )
    if after_class_problems:
        if has_current_after and has_previous_after and previous_training is not None:
            previous_rank_records = _load_rank_records(client, previous_training.training_id)
            after_class_rank_records = _merge_rank_records(
                rank_records, previous_rank_records
            )
        elif has_previous_after and previous_training is not None:
            after_class_rank_records = _load_rank_records(client, previous_training.training_id)
        elif has_current_after:
            after_class_rank_records = rank_records

    download_dir = ROOT / ".generated"
    download_dir.mkdir(parents=True, exist_ok=True)
    request = ReportRequest(
        team_name=team.name,
        training_name=training.title,
        problem_queries=[problem.title for problem in selected_problems],
        template_path=config.template_path,
        output_dir=download_dir,
        after_class_problem_queries=[problem.title for problem in after_class_problems],
    )
    output_path = build_output_path(request)
    rows = build_progress_rows(
        students,
        selected_problems,
        rank_records,
        after_class_problems=after_class_problems,
        after_class_rank_records=after_class_rank_records,
    )
    render_report(
        request=request,
        problems=selected_problems,
        after_class_problems=after_class_problems,
        rows=rows,
        output_path=output_path,
    )
    download_id = uuid.uuid4().hex
    state.downloads[download_id] = output_path
    return {"downloadUrl": f"/api/downloads/{download_id}", "filename": output_path.name}


def save_students(payload: dict) -> dict:
    group_id = int(payload.get("teamId") or 0)
    filename = str(payload.get("filename") or "").strip()
    records = payload.get("students")
    if not group_id:
        raise MatchError("请选择团队")
    if not filename:
        raise MatchError("请填写保存文件名")
    if not isinstance(records, list) or not records:
        raise MatchError("请至少选择一名学生")
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        raise MatchError("文件名必须是当前目录下的 .json 文件，例如 students.6-4.json")

    team = _find_team(group_id)
    students: list[dict] = []
    seen_uids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        uid = str(record.get("uid") or "").strip()
        username = str(record.get("username") or "").strip()
        nickname = str(record.get("nickname") or "").strip()
        real_name = str(record.get("realName") or record.get("real_name") or nickname).strip()
        if not uid or not username or not nickname or uid in seen_uids:
            continue
        seen_uids.add(uid)
        students.append(
            {
                "uid": uid,
                "username": username,
                "nickname": nickname,
                "real_name": real_name or nickname,
            }
        )

    if not students:
        raise MatchError("选择的学生数据不完整，无法保存")

    output_path = (PROJECT_ROOT / filename).resolve()
    if output_path.parent != PROJECT_ROOT:
        raise MatchError("学生 JSON 只能保存到项目根目录")
    payload_to_write = {
        "team_gid": group_id,
        "team_name": team.name,
        "students": students,
    }
    output_path.write_text(
        json.dumps(payload_to_write, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"path": str(output_path), "count": len(students)}


class TeachingToolboxHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/teams":
                self.write_json({"teams": list_teams()})
                return
            if parsed.path == "/api/trainings":
                query = parse_qs(parsed.query)
                group_id = int(query.get("groupId", [""])[0])
                self.write_json({"trainings": list_trainings(group_id)})
                return
            if parsed.path == "/api/students":
                query = parse_qs(parsed.query)
                group_id = int(query.get("groupId", [""])[0])
                self.write_json({"students": list_students(group_id)})
                return
            if parsed.path == "/api/problems":
                query = parse_qs(parsed.query)
                group_id = int(query.get("groupId", ["0"])[0])
                training_id = int(query.get("trainingId", [""])[0])
                password = query.get("trainingPassword", [""])[0].strip()
                include_previous = query.get("includePrevious", ["0"])[0] == "1"
                self.write_json(
                    {
                        "problems": list_problem_choices(
                            group_id,
                            training_id,
                            password,
                            include_previous,
                        )
                    }
                )
                return
            if parsed.path.startswith("/api/downloads/"):
                download_id = parsed.path.rsplit("/", 1)[-1]
                self.serve_download(download_id)
                return
            self.serve_static(parsed.path)
        except PermissionError as exc:
            self.write_json({"error": str(exc)}, status=401)
        except (AuthError, OJApiError, MatchError, FileNotFoundError, ValueError) as exc:
            self.write_json({"error": str(exc)}, status=500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/reports":
                payload = self.read_json_body()
                self.write_json(generate_report(payload))
                return
            if parsed.path == "/api/students-json":
                payload = self.read_json_body()
                self.write_json(save_students(payload))
                return
            self.write_json({"error": f"接口不存在: {parsed.path}"}, status=404)
        except PermissionError as exc:
            self.write_json({"error": str(exc)}, status=401)
        except (AuthError, OJApiError, MatchError, FileNotFoundError, ValueError) as exc:
            self.write_json({"error": str(exc)}, status=500)

    def serve_static(self, request_path: str) -> None:
        relative_path = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        file_path = (ROOT / relative_path).resolve()
        if not file_path.is_file() or ROOT not in file_path.parents:
            self.send_error(404)
            return

        payload = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def serve_download(self, download_id: str) -> None:
        file_path = state.downloads.get(download_id)
        if file_path is None or not file_path.exists():
            self.send_error(404)
            return
        payload = file_path.read_bytes()
        filename = quote(file_path.name)
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{filename}")
        self.end_headers()
        self.wfile.write(payload)

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8") or "{}")

    def write_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local teaching toolbox web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5173)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), TeachingToolboxHandler)
    print(f"Teaching toolbox: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
