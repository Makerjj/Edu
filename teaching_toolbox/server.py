from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
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
    _sort_students_by_name,
    build_output_path,
    _ensure_training_registered,
    find_previous_training,
    _needs_training_registration,
    _scan_teams_by_name,
)
from src.xdf_report.config import load_config
from src.xdf_report.excel_template import render_report
from src.xdf_report.matcher import MatchError
from src.xdf_report.models import Problem, ReportRequest, Team, Training
from src.xdf_report.report_data import build_progress_rows
from src.agent_studio.service import AGENT_TOOL_REGISTRY, create_agent_run, list_agent_runs
from src.problem_bank.service import ProblemBankSearch, search_problem_bank


@dataclass
class UserSession:
    session_id: str
    user_id: int
    account: str
    client: OJClient
    teams: list[dict] | None = None
    trainings_by_team: dict[int, list[dict]] = field(default_factory=dict)
    students_by_team: dict[int, list[dict]] = field(default_factory=dict)
    problems_by_training: dict[tuple[int, str], list[dict]] = field(default_factory=dict)


class AppState:
    config = None
    sessions: dict[str, UserSession] = {}
    downloads: dict[str, Path] = {}


state = AppState()
COOKIE_NAME = "teaching_toolbox_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7
DATA_DIR = ROOT / ".data"
DB_PATH = DATA_DIR / "toolbox.sqlite3"
SECRET_KEY_PATH = DATA_DIR / "secret.key"
AGENT_RUNS_DIR = ROOT / ".agent_runs"
SHORT_SESSION_AGE = timedelta(hours=12)
REMEMBER_SESSION_AGE = timedelta(days=7)


def get_config():
    if state.config is None:
        state.config = load_config(PROJECT_ROOT / "config.json")
    return state.config


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value)


def ensure_secret_key() -> bytes:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not SECRET_KEY_PATH.exists():
        SECRET_KEY_PATH.write_bytes(os.urandom(32))
        SECRET_KEY_PATH.chmod(0o600)
    return SECRET_KEY_PATH.read_bytes()


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right))


def _password_keystream(key: bytes, nonce: bytes, size: int) -> bytes:
    blocks: list[bytes] = []
    counter = 0
    while sum(len(block) for block in blocks) < size:
        counter_bytes = counter.to_bytes(4, "big")
        blocks.append(hmac.new(key, nonce + counter_bytes, hashlib.sha256).digest())
        counter += 1
    return b"".join(blocks)[:size]


def encrypt_password(password: str) -> str:
    # Stdlib-only local encryption: the key lives in .data/secret.key, outside Git.
    key = ensure_secret_key()
    nonce = os.urandom(16)
    plain = password.encode("utf-8")
    cipher = _xor_bytes(plain, _password_keystream(key, nonce, len(plain)))
    tag = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    return "v1:" + base64.urlsafe_b64encode(nonce + tag + cipher).decode("ascii")


def decrypt_password(value: str) -> str:
    if not value.startswith("v1:"):
        raise ValueError("不支持的密码加密格式")
    key = ensure_secret_key()
    raw = base64.urlsafe_b64decode(value[3:].encode("ascii"))
    nonce, tag, cipher = raw[:16], raw[16:48], raw[48:]
    expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected):
        raise ValueError("密码数据校验失败")
    plain = _xor_bytes(cipher, _password_keystream(key, nonce, len(cipher)))
    return plain.decode("utf-8")


def db_connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with db_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account TEXT NOT NULL UNIQUE,
                account_masked TEXT NOT NULL,
                encrypted_password TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_id TEXT NOT NULL UNIQUE,
                oj_token TEXT NOT NULL,
                remember INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )


def upsert_user(account: str, password: str) -> int:
    init_db()
    now = utc_iso(utc_now())
    encrypted_password = encrypt_password(password)
    with db_connect() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE account = ?",
            (account,),
        ).fetchone()
        if row is None:
            cursor = conn.execute(
                """
                INSERT INTO users (account, account_masked, encrypted_password, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (account, mask_account(account), encrypted_password, now, now),
            )
            return int(cursor.lastrowid)
        user_id = int(row["id"])
        conn.execute(
            """
            UPDATE users
            SET account_masked = ?, encrypted_password = ?, updated_at = ?
            WHERE id = ?
            """,
            (mask_account(account), encrypted_password, now, user_id),
        )
        return user_id


def create_session(
    user_id: int, account: str, oj_token: str, remember: bool
) -> str:
    init_db()
    session_id = uuid.uuid4().hex
    now = utc_now()
    expires_at = now + (REMEMBER_SESSION_AGE if remember else SHORT_SESSION_AGE)
    with db_connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                user_id, session_id, oj_token, remember, created_at, last_seen_at, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                session_id,
                oj_token,
                1 if remember else 0,
                utc_iso(now),
                utc_iso(now),
                utc_iso(expires_at),
            ),
        )
    state.sessions[session_id] = UserSession(
        session_id=session_id,
        user_id=user_id,
        account=account,
        client=OJClient(oj_token),
    )
    return session_id


def restore_session(session_id: str | None) -> UserSession | None:
    if not session_id:
        return None
    session = state.sessions.get(session_id)
    if session is not None:
        if not session_is_valid(session_id):
            state.sessions.pop(session_id, None)
            return None
        touch_session(session_id)
        return session

    init_db()
    now = utc_now()
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT sessions.session_id, sessions.user_id, sessions.oj_token, sessions.expires_at,
                   users.account
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        if parse_utc(str(row["expires_at"])) <= now:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return None
        conn.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE session_id = ?",
            (utc_iso(now), session_id),
        )

    restored = UserSession(
        session_id=str(row["session_id"]),
        user_id=int(row["user_id"]),
        account=str(row["account"]),
        client=OJClient(str(row["oj_token"])),
    )
    state.sessions[session_id] = restored
    return restored


def touch_session(session_id: str) -> None:
    init_db()
    with db_connect() as conn:
        conn.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE session_id = ?",
            (utc_iso(utc_now()), session_id),
        )


def session_is_valid(session_id: str) -> bool:
    init_db()
    with db_connect() as conn:
        row = conn.execute(
            "SELECT expires_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return False
        if parse_utc(str(row["expires_at"])) <= utc_now():
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return False
    return True


def delete_session(session_id: str) -> None:
    state.sessions.pop(session_id, None)
    init_db()
    with db_connect() as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def fetch_oj_token(account: str, password: str) -> str:
    auth_client = DingdangAuthClient()
    dingdang_token = auth_client.login(account, password)
    student_code = _extract_student_code(auth_client.get_students(dingdang_token))
    auth_session = auth_client.login_oj(dingdang_token, student_code)
    return auth_session.oj_token


def login_user(account: str, password: str, remember: bool) -> str:
    oj_token = fetch_oj_token(account, password)
    init_db()
    user_id = upsert_user(account, password)
    return create_session(user_id, account, oj_token, remember)


def load_saved_password(user_id: int) -> str:
    init_db()
    with db_connect() as conn:
        row = conn.execute(
            "SELECT encrypted_password FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        raise PermissionError("登录信息不存在，请重新登录")
    return decrypt_password(str(row["encrypted_password"]))


def update_session_oj_token(session: UserSession, oj_token: str) -> None:
    session.client = OJClient(oj_token)
    init_db()
    with db_connect() as conn:
        conn.execute(
            "UPDATE sessions SET oj_token = ?, last_seen_at = ? WHERE session_id = ?",
            (oj_token, utc_iso(utc_now()), session.session_id),
        )


def renew_session_token(session: UserSession) -> None:
    password = load_saved_password(session.user_id)
    update_session_oj_token(session, fetch_oj_token(session.account, password))


def looks_like_oj_login_expired(exc: OJApiError) -> bool:
    message = str(exc).lower()
    markers = (
        "401",
        "403",
        "unauthorized",
        "forbidden",
        "authorization",
        "token",
        "未登录",
        "登录过期",
        "鉴权",
        "认证",
    )
    return any(marker in message for marker in markers)


def public_error_message(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if isinstance(exc, PermissionError):
        return text or "请先登录。"
    if isinstance(exc, AuthError):
        if "登录钉钉" in text or "登录失败" in text:
            return "登录失败，请检查手机号和密码是否正确。"
        if "未获取到 OJ Authorization" in text:
            return "登录失败，暂时没有获取到 OJ 授权，请稍后重试。"
        return "登录服务暂时不可用，请稍后重试。"
    if isinstance(exc, OJApiError):
        if "该训练属于私有" in text or "该训练需要训练密码" in text:
            return "该训练需要训练密码，请填写正确密码后再试。"
        if looks_like_oj_login_expired(exc):
            return "登录状态已失效，请重新登录。"
        if "get /get-training-problem-list" in lowered:
            return "题目加载失败，请检查训练是否可访问。"
        if "get /training-rank" in lowered:
            return "成绩数据加载失败，请稍后重试。"
        return "OJ 服务暂时不可用，请稍后重试。"
    if isinstance(exc, MatchError):
        return text or "选择内容不完整，请检查后重试。"
    if isinstance(exc, FileNotFoundError):
        return "系统模板文件缺失，请联系管理员处理。"
    if isinstance(exc, ValueError):
        return "填写内容格式不正确，请检查后重试。"
    return "操作没有完成，请稍后重试。"


def run_with_oj_retry(session: UserSession, operation):
    try:
        return operation()
    except OJApiError as exc:
        if not looks_like_oj_login_expired(exc):
            raise
        renew_session_token(session)
        try:
            return operation()
        except OJApiError as retry_exc:
            if looks_like_oj_login_expired(retry_exc):
                delete_session(session.session_id)
                raise PermissionError("登录已过期，请重新登录") from retry_exc
            raise


def mask_account(account: str) -> str:
    if len(account) < 7:
        return account
    return f"{account[:3]}****{account[-4:]}"


def list_teams(session: UserSession) -> list[dict]:
    if session.teams is not None:
        return session.teams

    teams = _scan_teams_by_name(session.client, "", 5000, 25)
    session.teams = [
        {"groupId": team.group_id, "name": team.name}
        for team in sorted(teams, key=lambda item: item.group_id)
    ]
    return session.teams


def list_trainings(session: UserSession, group_id: int) -> list[dict]:
    if group_id not in session.trainings_by_team:
        trainings = _load_trainings(session.client, group_id)
        session.trainings_by_team[group_id] = [
            {"trainingId": training.training_id, "title": training.title}
            for training in trainings
        ]
    return session.trainings_by_team[group_id]


def list_students(session: UserSession, group_id: int) -> list[dict]:
    if group_id not in session.students_by_team:
        students = _sort_students_by_name(_load_students(session.client, group_id))
        rows: list[dict] = []
        for student in students:
            profile = _load_student_profile(session.client, student.uid, student.username)
            rows.append(
                {
                    "uid": student.uid,
                    "username": student.username,
                    "nickname": student.nickname,
                    "realName": student.nickname,
                    "school": profile.get("school", ""),
                    "phone": profile.get("phone", ""),
                }
            )
        session.students_by_team[group_id] = rows
    return session.students_by_team[group_id]


def _load_student_profile(client: OJClient, uid: str, username: str) -> dict:
    payload = client.get(
        "/get-user-home-info",
        {"uid": uid, "username": username},
    )
    data = payload.get("data", {})
    if not isinstance(data, dict):
        return {}
    return {
        "school": str(data.get("school") or "").strip(),
        "phone": str(
            data.get("phone")
            or data.get("mobile")
            or data.get("tel")
            or data.get("telephone")
            or ""
        ).strip(),
    }


def saved_students_filename(group_id: int) -> str:
    return f"students.{group_id}.json"


def saved_students_path(group_id: int) -> Path:
    return PROJECT_ROOT / saved_students_filename(group_id)


def list_saved_students(group_id: int) -> dict:
    path = saved_students_path(group_id)
    if not path.exists():
        return {"exists": False, "path": str(path), "students": [], "count": 0}
    students = []
    raw_payload = json.loads(path.read_text(encoding="utf-8"))
    for record in raw_payload.get("students", []):
        if not isinstance(record, dict):
            continue
        uid = str(record.get("uid") or "").strip()
        username = str(record.get("username") or "").strip()
        nickname = str(record.get("nickname") or "").strip()
        real_name = str(record.get("real_name") or record.get("realName") or nickname).strip()
        school = str(record.get("school") or record.get("academy") or "").strip()
        phone = str(record.get("phone") or record.get("mobile") or "").strip()
        if not uid or not username or not nickname:
            continue
        students.append(
            {
                "uid": uid,
                "username": username,
                "nickname": nickname,
                "realName": real_name or nickname,
                "school": school,
                "phone": phone,
            }
        )
    return {
        "exists": True,
        "path": str(path),
        "students": students,
        "count": len(students),
    }


def list_problems(
    session: UserSession, training_id: int, training_password: str
) -> list[dict]:
    cache_key = (training_id, training_password)
    if cache_key in session.problems_by_training:
        return session.problems_by_training[cache_key]

    try:
        problems = _load_problems(session.client, training_id)
    except OJApiError as exc:
        if not _needs_training_registration(exc):
            raise
        try:
            renew_session_token(session)
            problems = _load_problems(session.client, training_id)
        except OJApiError as refreshed_exc:
            if not _needs_training_registration(refreshed_exc):
                raise
            exc = refreshed_exc
        else:
            session.problems_by_training[cache_key] = [
                {"problemId": problem.problem_id, "title": problem.title}
                for problem in problems
            ]
            return session.problems_by_training[cache_key]
        if not training_password:
            raise PermissionError("该训练属于私有训练，请先填写训练密码") from exc
        _ensure_training_registered(session.client, training_id, training_password)
        problems = _load_problems(session.client, training_id)

    session.problems_by_training[cache_key] = [
        {"problemId": problem.problem_id, "title": problem.title}
        for problem in problems
    ]
    return session.problems_by_training[cache_key]


def list_problem_choices(
    session: UserSession,
    group_id: int,
    training_id: int,
    training_password: str,
    include_previous: bool,
) -> list[dict]:
    choices = [
        {**problem, "source": problem.get("source", "current")}
        for problem in list_problems(session, training_id, training_password)
    ]
    if not include_previous:
        return choices

    trainings = _load_trainings(session.client, group_id)
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
            session, previous_training.training_id, training_password
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


def _find_team(session: UserSession, group_id: int) -> Team:
    for team in list_teams(session):
        if int(team["groupId"]) == group_id:
            return Team(group_id=group_id, name=str(team["name"]))
    raise MatchError(f"未找到团队 gid={group_id}")


def _find_training(session: UserSession, group_id: int, training_id: int) -> Training:
    for training in list_trainings(session, group_id):
        if int(training["trainingId"]) == training_id:
            return Training(training_id=training_id, title=str(training["title"]))
    raise MatchError(f"未找到训练 tid={training_id}")


def generate_report(session: UserSession, payload: dict) -> dict:
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

    team = _find_team(session, group_id)
    training = _find_training(session, group_id, training_id)
    current_problem_payloads = list_problems(session, training_id, training_password)
    current_problems = [_problem_from_payload(item) for item in current_problem_payloads]
    selected_problems = [
        problem for problem in current_problems if problem.title in set(problem_titles)
    ]
    if len(selected_problems) != len(set(problem_titles)):
        raise MatchError("部分课堂题目不在当前训练中，请重新选择")

    trainings = [
        Training(training_id=int(item["trainingId"]), title=str(item["title"]))
        for item in list_trainings(session, group_id)
    ]
    previous_training = find_previous_training(trainings, training)
    previous_problem_payloads: list[dict] = []
    if previous_training is not None:
        try:
            previous_problem_payloads = list_problems(
                session, previous_training.training_id, training_password
            )
        except PermissionError:
            previous_problem_payloads = []
    after_lookup = {
        item["title"]: _problem_from_payload(item)
        for item in previous_problem_payloads
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
        students = _sort_students_by_name(_load_students(session.client, group_id))
    rank_records = _load_rank_records(session.client, training_id)
    after_class_rank_records: list[dict] = []
    if after_class_problems and previous_training is not None:
        after_class_rank_records = _load_rank_records(session.client, previous_training.training_id)

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


def save_students(session: UserSession, payload: dict) -> dict:
    group_id = int(payload.get("teamId") or 0)
    filename = str(payload.get("filename") or "").strip()
    records = payload.get("students")
    if not group_id:
        raise MatchError("请选择团队")
    if not filename:
        filename = saved_students_filename(group_id)
    if not isinstance(records, list) or not records:
        raise MatchError("请至少选择一名学生")
    if "/" in filename or "\\" in filename or not filename.endswith(".json"):
        raise MatchError("学生名单保存失败，请刷新页面后重试")

    team = _find_team(session, group_id)
    students: list[dict] = []
    seen_uids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        uid = str(record.get("uid") or "").strip()
        username = str(record.get("username") or "").strip()
        nickname = str(record.get("nickname") or "").strip()
        real_name = str(record.get("realName") or record.get("real_name") or nickname).strip()
        school = str(record.get("school") or record.get("academy") or "").strip()
        phone = str(record.get("phone") or record.get("mobile") or "").strip()
        if not uid or not username or not nickname or uid in seen_uids:
            continue
        seen_uids.add(uid)
        students.append(
            {
                "uid": uid,
                "username": username,
                "nickname": nickname,
                "real_name": real_name or nickname,
                "school": school,
                "phone": phone,
            }
        )

    if not students:
        raise MatchError("选择的学生数据不完整，无法保存")

    output_path = (PROJECT_ROOT / filename).resolve()
    if output_path.parent != PROJECT_ROOT:
        raise MatchError("学生名单保存失败，请刷新页面后重试")
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

    def current_session_id(self) -> str | None:
        raw_cookie = self.headers.get("Cookie")
        if not raw_cookie:
            return None
        cookie = SimpleCookie(raw_cookie)
        morsel = cookie.get(COOKIE_NAME)
        if morsel is None:
            return None
        return morsel.value

    def current_session(self) -> UserSession:
        session = restore_session(self.current_session_id())
        if session is None:
            raise PermissionError("请先登录")
        return session

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/me":
                session = restore_session(self.current_session_id())
                if session is None:
                    self.write_json({"loggedIn": False})
                else:
                    self.write_json(
                        {
                            "loggedIn": True,
                            "account": mask_account(session.account),
                        }
                    )
                return
            if parsed.path == "/api/teams":
                session = self.current_session()
                self.write_json(
                    {"teams": run_with_oj_retry(session, lambda: list_teams(session))}
                )
                return
            if parsed.path == "/api/trainings":
                session = self.current_session()
                query = parse_qs(parsed.query)
                group_id = int(query.get("groupId", [""])[0])
                self.write_json(
                    {
                        "trainings": run_with_oj_retry(
                            session, lambda: list_trainings(session, group_id)
                        )
                    }
                )
                return
            if parsed.path == "/api/students":
                session = self.current_session()
                query = parse_qs(parsed.query)
                group_id = int(query.get("groupId", [""])[0])
                self.write_json(
                    {
                        "students": run_with_oj_retry(
                            session, lambda: list_students(session, group_id)
                        )
                    }
                )
                return
            if parsed.path == "/api/saved-students":
                self.current_session()
                query = parse_qs(parsed.query)
                group_id = int(query.get("groupId", [""])[0])
                if not group_id:
                    raise MatchError("请选择团队")
                self.write_json(list_saved_students(group_id))
                return
            if parsed.path == "/api/problems":
                session = self.current_session()
                query = parse_qs(parsed.query)
                group_id = int(query.get("groupId", ["0"])[0])
                training_id = int(query.get("trainingId", [""])[0])
                password = query.get("trainingPassword", [""])[0].strip()
                include_previous = query.get("includePrevious", ["0"])[0] == "1"
                self.write_json(
                    {
                        "problems": run_with_oj_retry(
                            session,
                            lambda: list_problem_choices(
                                session,
                                group_id,
                                training_id,
                                password,
                                include_previous,
                            ),
                        )
                    }
                )
                return
            if parsed.path == "/api/problem-bank/search":
                session = self.current_session()
                query = parse_qs(parsed.query)
                search_query = query.get("query", [""])[0]
                limit = int(query.get("limit", ["8"])[0] or 8)
                include_detail = query.get("includeDetail", ["1"])[0] != "0"
                self.write_json(
                    run_with_oj_retry(
                        session,
                        lambda: search_problem_bank(
                            session.client,
                            ProblemBankSearch(
                                query=search_query,
                                limit=limit,
                                include_detail=include_detail,
                            ),
                        ),
                    )
                )
                return
            if parsed.path == "/api/agent/tools":
                self.current_session()
                self.write_json({"tools": AGENT_TOOL_REGISTRY})
                return
            if parsed.path == "/api/agent/runs":
                self.current_session()
                self.write_json({"runs": list_agent_runs(AGENT_RUNS_DIR)})
                return
            if parsed.path.startswith("/api/downloads/"):
                download_id = parsed.path.rsplit("/", 1)[-1]
                self.serve_download(download_id)
                return
            self.serve_static(parsed.path)
        except PermissionError as exc:
            self.write_json({"error": public_error_message(exc)}, status=401)
        except (AuthError, OJApiError, MatchError, FileNotFoundError, ValueError) as exc:
            self.write_json({"error": public_error_message(exc)}, status=500)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/login":
                payload = self.read_json_body()
                account = str(payload.get("account") or "").strip()
                password = str(payload.get("password") or "").strip()
                remember = bool(payload.get("remember"))
                if not account or not password:
                    raise MatchError("请填写手机号和密码")
                if not account.isdigit() or len(account) != 11:
                    raise MatchError("请输入 11 位 OJ 手机号")
                session_id = login_user(account, password, remember)
                session = state.sessions[session_id]
                self.write_json(
                    {
                        "loggedIn": True,
                        "account": mask_account(session.account),
                    },
                    cookies=[self._session_cookie_value(session_id, remember)],
                )
                return
            if parsed.path == "/api/logout":
                session_id = self.current_session_id()
                if session_id:
                    delete_session(session_id)
                self.write_json(
                    {"loggedIn": False},
                    cookies=[self._clear_session_cookie_value()],
                )
                return
            if parsed.path == "/api/reports":
                session = self.current_session()
                payload = self.read_json_body()
                self.write_json(
                    run_with_oj_retry(session, lambda: generate_report(session, payload))
                )
                return
            if parsed.path == "/api/students-json":
                session = self.current_session()
                payload = self.read_json_body()
                self.write_json(
                    run_with_oj_retry(session, lambda: save_students(session, payload))
                )
                return
            if parsed.path == "/api/agent/runs":
                self.current_session()
                payload = self.read_json_body()
                self.write_json(create_agent_run(payload, AGENT_RUNS_DIR))
                return
            self.write_json({"error": "页面请求不存在，请刷新页面后重试。"}, status=404)
        except PermissionError as exc:
            self.write_json({"error": public_error_message(exc)}, status=401)
        except (AuthError, OJApiError, MatchError, FileNotFoundError, ValueError) as exc:
            self.write_json({"error": public_error_message(exc)}, status=500)

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

    def _session_cookie_value(self, session_id: str, remember: bool) -> str:
        cookie = f"{COOKIE_NAME}={session_id}; Path=/; SameSite=Lax; HttpOnly"
        if remember:
            cookie += f"; Max-Age={COOKIE_MAX_AGE}"
        return cookie

    def _clear_session_cookie_value(self) -> str:
        return f"{COOKIE_NAME}=; Path=/; SameSite=Lax; HttpOnly; Max-Age=0"

    def write_json(
        self, payload: dict, status: int = 200, cookies: list[str] | None = None
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local teaching toolbox web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    init_db()
    server = ThreadingHTTPServer((args.host, args.port), TeachingToolboxHandler)
    print(f"Teaching toolbox: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
