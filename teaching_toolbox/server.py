from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell

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
    _load_teams,
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
from src.xdf_report.matcher import MatchError, match_problem_queries
from src.xdf_report.models import Problem, ReportRequest, Team, Training
from src.xdf_report.report_data import build_progress_rows
from src.agent_studio.service import AGENT_TOOL_REGISTRY, create_agent_run, list_agent_runs
from src.problem_bank.service import ProblemBankSearch, search_local_problem_bank, search_problem_bank


@dataclass
class UserSession:
    session_id: str
    user_id: int
    account: str
    client: OJClient
    remember: bool = False
    teams: list[dict] | None = None
    trainings_by_team: dict[int, list[dict]] = field(default_factory=dict)
    students_by_team: dict[int, list[dict]] = field(default_factory=dict)
    problems_by_training: dict[tuple[int, str], list[dict]] = field(default_factory=dict)
    reports: dict[str, dict] = field(default_factory=dict)
    downloads: dict[str, Path] = field(default_factory=dict)


class AppState:
    config = None
    sessions: dict[str, UserSession] = {}


state = AppState()
COOKIE_NAME = "teaching_toolbox_session"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365
DATA_DIR = ROOT / ".data"
DB_PATH = DATA_DIR / "toolbox.sqlite3"
SECRET_KEY_PATH = DATA_DIR / "secret.key"
AGENT_RUNS_DIR = ROOT / ".agent_runs"
CODEX_BIN = "/opt/homebrew/bin/codex"
FEEDBACK_SKILL_PATH = PROJECT_ROOT.parent / "skills" / "after-class-feedback" / "SKILL.md"
SHORT_SESSION_AGE = timedelta(hours=12)
REMEMBER_SESSION_AGE = timedelta(days=365)


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
    expires_at = session_expires_at(now, remember)
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
        remember=remember,
    )
    return session_id


def session_expires_at(now: datetime, remember: bool) -> datetime:
    return now + (REMEMBER_SESSION_AGE if remember else SHORT_SESSION_AGE)


def touch_session_with_connection(
    conn: sqlite3.Connection, session_id: str, now: datetime, remember: bool
) -> None:
    if remember:
        conn.execute(
            "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE session_id = ?",
            (utc_iso(now), utc_iso(session_expires_at(now, True)), session_id),
        )
    else:
        conn.execute(
            "UPDATE sessions SET last_seen_at = ? WHERE session_id = ?",
            (utc_iso(now), session_id),
        )


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
            SELECT sessions.session_id, sessions.user_id, sessions.oj_token,
                   sessions.remember, sessions.expires_at,
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
        touch_session_with_connection(conn, session_id, now, bool(row["remember"]))

    restored = UserSession(
        session_id=str(row["session_id"]),
        user_id=int(row["user_id"]),
        account=str(row["account"]),
        client=OJClient(str(row["oj_token"])),
        remember=bool(row["remember"]),
    )
    state.sessions[session_id] = restored
    return restored


def restore_latest_remembered_session() -> UserSession | None:
    init_db()
    now = utc_iso(utc_now())
    with db_connect() as conn:
        row = conn.execute(
            """
            SELECT session_id
            FROM sessions
            WHERE remember = 1 AND expires_at > ?
            ORDER BY last_seen_at DESC, id DESC
            LIMIT 1
            """,
            (now,),
        ).fetchone()
    if row is None:
        return None
    return restore_session(str(row["session_id"]))


def touch_session(session_id: str) -> None:
    init_db()
    now = utc_now()
    with db_connect() as conn:
        row = conn.execute(
            "SELECT remember FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return
        touch_session_with_connection(conn, session_id, now, bool(row["remember"]))


def session_is_valid(session_id: str) -> bool:
    init_db()
    now = utc_now()
    with db_connect() as conn:
        row = conn.execute(
            "SELECT expires_at, remember FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return False
        if parse_utc(str(row["expires_at"])) <= now:
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return False
        if bool(row["remember"]):
            touch_session_with_connection(conn, session_id, now, True)
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

    try:
        teams = _load_teams(session.client, "")
        if not teams:
            renew_session_token(session)
            teams = _load_teams(session.client, "")
    except OJApiError:
        try:
            renew_session_token(session)
            teams = _load_teams(session.client, "")
        except OJApiError:
            teams = _scan_teams_by_name(session.client, "", 5000, 25)
    session.teams = [
        {"groupId": team.group_id, "name": team.name}
        for team in sorted(teams, key=lambda item: item.group_id)
    ]
    return session.teams


def list_trainings(session: UserSession, group_id: int) -> list[dict]:
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


def decode_feedback_image(payload: dict) -> tuple[bytes, str]:
    image_data = str(payload.get("imageData") or "").strip()
    if not image_data.startswith("data:image/") or ";base64," not in image_data:
        raise MatchError("请上传图片截图")
    header, encoded = image_data.split(",", 1)
    image_type = header.split(";", 1)[0].split("/", 1)[-1].lower()
    if image_type not in {"png", "jpeg", "jpg", "webp"}:
        raise MatchError("仅支持 PNG、JPG 或 WebP 图片")
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except ValueError as exc:
        raise MatchError("图片内容解析失败，请重新上传") from exc
    if not image_bytes:
        raise MatchError("图片内容为空，请重新上传")
    return image_bytes, "jpg" if image_type == "jpeg" else image_type


def _parse_codex_summary(raw_output: str) -> dict:
    text = raw_output.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MatchError("Codex agent 没有返回可解析的总结，请重试") from exc
    topic = str(payload.get("topic") or "").strip()
    knowledge_points = str(payload.get("knowledgePoints") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    if not topic and not knowledge_points:
        raise MatchError("Codex agent 没有识别出课程主题或知识点，请换一张截图")
    return {
        "topic": topic,
        "knowledgePoints": knowledge_points,
        "summary": summary,
    }


def _parse_feedback_check(raw_output: str) -> dict:
    text = raw_output.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MatchError("Codex agent 没有返回可解析的检查结果，请重试") from exc
    status = str(payload.get("status") or "needs_review").strip()
    issues = payload.get("issues") or []
    suggestions = payload.get("suggestions") or []
    if not isinstance(issues, list) or not isinstance(suggestions, list):
        raise MatchError("Codex agent 检查结果格式不正确，请重试")
    normalized_issues = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        normalized_issues.append(
            {
                "type": str(issue.get("type") or "other").strip(),
                "severity": str(issue.get("severity") or "medium").strip(),
                "message": str(issue.get("message") or "").strip(),
                "quote": str(issue.get("quote") or "").strip(),
                "suggestion": str(issue.get("suggestion") or "").strip(),
            }
        )
    return {
        "status": status,
        "issues": normalized_issues,
        "suggestions": [str(item).strip() for item in suggestions if str(item).strip()],
        "summary": str(payload.get("summary") or "").strip(),
    }


def _parse_generated_feedback(raw_output: str) -> dict:
    feedback = raw_output.strip()
    if not feedback:
        raise MatchError("Codex agent 没有返回反馈内容，请重试")
    return {"feedback": feedback}


def _parse_revised_feedback(raw_output: str) -> dict:
    text = raw_output.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MatchError("Codex agent 没有返回可解析的修改结果，请重试") from exc
    feedback = str(payload.get("feedback") or "").strip()
    message = str(payload.get("message") or "已按你的要求修改反馈。").strip()
    if not feedback:
        raise MatchError("Codex agent 没有返回修改后的反馈，请重试")
    return {"feedback": feedback, "message": message}


def _walk_text_values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            texts.extend(_walk_text_values(item))
        return texts
    if isinstance(value, dict):
        texts: list[str] = []
        for item in value.values():
            texts.extend(_walk_text_values(item))
        return texts
    return []


def load_feedback_skill_excerpt(limit: int = 4500) -> str:
    try:
        return FEEDBACK_SKILL_PATH.read_text(encoding="utf-8")[:limit].strip()
    except OSError:
        return ""


def check_feedback_text_with_codex(payload: dict) -> dict:
    feedback = str(payload.get("feedback") or "").strip()
    if not feedback:
        raise MatchError("请先生成或填写要检查的反馈")
    student_name = str(payload.get("studentName") or "").strip()
    username = str(payload.get("username") or "").strip()
    topic = str(payload.get("topic") or "").strip()
    level = str(payload.get("level") or "").strip()
    skill_excerpt = load_feedback_skill_excerpt()
    prompt = (
        "你是课后反馈质检员。请严格检查下面这条中文课后反馈是否存在错误。"
        "你必须参考 after-class-feedback skill 的规则和检查清单。"
        "重点检查：真实学生名泄露、把别的学生名字写进反馈、家长称呼错误、"
        "错别字、语病、标点异常、占位符错误、课程知识点不一致、"
        "没有证据的课堂表现或作业完成情况、夸张评价、直接否定孩子能力、"
        "表现等级和文案语气不匹配、反馈结构缺失、重复啰嗦。"
        "只返回 JSON，不要输出解释。"
        "JSON 格式："
        '{"status":"ok|needs_fix|needs_review",'
        '"issues":[{"type":"name|typo|fact|tone|placeholder|structure|level|other",'
        '"severity":"low|medium|high","message":"问题说明","quote":"原文片段","suggestion":"修改建议"}],'
        '"suggestions":["整体修改建议"],"summary":"一句话检查结论"}。'
        "\n\n学生信息："
        f"\n- studentName: {student_name or '未提供'}"
        f"\n- username: {username or '未提供'}"
        f"\n- topic: {topic or '未提供'}"
        f"\n- level: {level or '未提供'}"
        f"\n\n反馈正文：\n{feedback}"
        f"\n\n参考 skill：\n{skill_excerpt}"
    )
    try:
        result = subprocess.run(
            [
                CODEX_BIN,
                "exec",
                "--skip-git-repo-check",
                "-",
            ],
            check=True,
            capture_output=True,
            text=True,
            input=prompt,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if not detail:
            detail = f"codex exec 退出码 {exc.returncode}"
        raise MatchError(f"Codex agent 检查失败：{detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MatchError("Codex agent 检查超时，请稍后重试") from exc
    return _parse_feedback_check(result.stdout)


def generate_feedback_with_codex(payload: dict) -> dict:
    student_name = str(payload.get("studentName") or "").strip()
    username = str(payload.get("username") or "").strip()
    details = str(payload.get("details") or "").strip()
    level = str(payload.get("level") or "").strip() or "中等"
    dimensions = payload.get("dimensions")
    if not isinstance(dimensions, dict) or not dimensions:
        raise MatchError("请先选择学生表现维度")

    skill_excerpt = load_feedback_skill_excerpt()
    prompt = (
        "你是编程课后反馈助手。请根据学生表现维度和课堂细节描述，"
        "为家长生成一段自然、真实、可直接发送的中文私人反馈。"
        "你必须参考 after-class-feedback skill 的规则。"
        "课堂内容反馈与学生私人反馈是两个独立对象。"
        "本次只生成学生私人反馈，不复述课程主题，不列知识点清单，"
        "也不得因为没有上传课堂截图而拒绝生成。"
        "课堂细节描述属于用户明确提供的学生表现证据，生成时优先使用；"
        "只润色和组织这些细节，不得补写细节中没有出现的课堂事实。"
        "只使用 include=true 的维度；include=false 的维度只作为背景，不写进最终反馈。"
        "不要编造课堂互动、作业完成情况、点名表扬或额外事实。"
        "直接输出反馈正文，不要输出 JSON，不要加解释。"
        "反馈必须包含 #沟通称呼语# 和 #学员昵称#。"
        "\n\n学生信息："
        f"\n- studentName: {student_name or '未提供'}"
        f"\n- username: {username or '未提供'}"
        f"\n- level: {level}"
        f"\n- details: {details or '未提供'}"
        f"\n\n维度原始数据(JSON)：\n{json.dumps(dimensions, ensure_ascii=False, indent=2)}"
        f"\n\n参考 skill：\n{skill_excerpt}"
    )
    try:
        result = subprocess.run(
            [
                CODEX_BIN,
                "exec",
                "--skip-git-repo-check",
                "-",
            ],
            check=True,
            capture_output=True,
            text=True,
            input=prompt,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if not detail:
            detail = f"codex exec 退出码 {exc.returncode}"
        raise MatchError(f"Codex agent 生成失败：{detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MatchError("Codex agent 生成超时，请稍后重试") from exc
    return _parse_generated_feedback(result.stdout)


def revise_feedback_with_codex(payload: dict) -> dict:
    feedback = str(payload.get("feedback") or "").strip()
    instruction = str(payload.get("instruction") or "").strip()
    details = str(payload.get("details") or "").strip()
    level = str(payload.get("level") or "").strip() or "中等"
    dimensions = payload.get("dimensions") or {}
    if not feedback:
        raise MatchError("请先生成或填写反馈")
    if not instruction:
        raise MatchError("请填写你希望怎样修改")

    skill_excerpt = load_feedback_skill_excerpt()
    prompt = (
        "你是正在网页里与老师沟通的课后反馈修改助手。"
        "请根据老师本轮提出的修改要求，修改现有的学生私人反馈。"
        "你必须参考 after-class-feedback skill，保留事实边界，不能新增未提供的课堂表现。"
        "课堂内容反馈与私人反馈分开，本次只修改私人反馈。"
        "所有学生姓名继续使用 #学员昵称#，家长称呼使用 #沟通称呼语#。"
        "只返回 JSON，不要输出 JSON 以外的文字。"
        'JSON 格式：{"message":"简短说明本次怎样修改", "feedback":"修改后的完整反馈"}。'
        f"\n\n老师的修改要求：\n{instruction}"
        f"\n\n现有反馈：\n{feedback}"
        f"\n\n已知课堂细节：\n{details or '未提供'}"
        f"\n\n表现等级：{level}"
        f"\n表现维度(JSON)：\n{json.dumps(dimensions, ensure_ascii=False, indent=2)}"
        f"\n\n参考 skill：\n{skill_excerpt}"
    )
    try:
        result = subprocess.run(
            [CODEX_BIN, "exec", "--skip-git-repo-check", "-"],
            check=True,
            capture_output=True,
            text=True,
            input=prompt,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        if not detail:
            detail = f"codex exec 退出码 {exc.returncode}"
        raise MatchError(f"Codex agent 修改失败：{detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise MatchError("Codex agent 修改超时，请稍后重试") from exc
    return _parse_revised_feedback(result.stdout)


def summarize_feedback_image_with_codex(payload: dict) -> dict:
    image_bytes, image_type = decode_feedback_image(payload)
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / f"lesson-shot.{image_type}"
        input_path.write_bytes(image_bytes)
        skill_excerpt = load_feedback_skill_excerpt()
        prompt = (
            "你是编程课后反馈助手。请观察这张课堂截图，总结本节课的课程主题，"
            "并生成可直接放进家长课后反馈里的完整知识点反馈文本。"
            "你必须参考本地课后反馈写作 skill 的风格和结构来写课堂内容反馈。"
            "不要做 OCR 原文转写，不要输出解释，只返回 JSON。"
            "JSON 格式必须是："
            '{"topic":"课程主题",'
            '"knowledgePoints":"完整知识点反馈文本",'
            '"summary":"一句话概括本节课内容"}。'
            "knowledgePoints 字段必须写成完整课堂内容反馈，参考这个结构："
            "#沟通称呼语#～本周课程主要讲了……这一模块内容，帮助学生理解……。\\n\\n"
            "本节课主要内容如下：\\n"
            "1. ……\\n2. ……\\n3. ……\\n\\n"
            "本节课的重难点是：\\n"
            "1. ……\\n2. ……\\n\\n"
            "课后可以重点复习：\\n"
            "1. ……\\n2. ……。"
            "要求：使用截图中的真实课程内容；不要输出孩子表现分档；"
            "不编造课堂表现、点名表扬或作业完成情况；"
            "所有学生姓名用 #学员昵称#，家长称呼用 #沟通称呼语#。"
            f"\n\n参考本地课后反馈写作 skill：\n{skill_excerpt}"
        )
        try:
            result = subprocess.run(
                [
                    CODEX_BIN,
                    "exec",
                    "--skip-git-repo-check",
                    "--image",
                    str(input_path),
                    "-",
                ],
                check=True,
                capture_output=True,
                text=True,
                input=prompt,
                timeout=120,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            if not detail:
                detail = f"codex exec 退出码 {exc.returncode}"
            raise MatchError(f"Codex agent 总结失败：{detail}") from exc
        except subprocess.TimeoutExpired as exc:
            raise MatchError("Codex agent 总结超时，请稍后重试") from exc
    return _parse_codex_summary(result.stdout)


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
    homework_only = payload.get("homeworkOnly") is True
    students_json = str(payload.get("studentsJson") or "").strip()
    problem_queries = [
        str(value).strip()
        for value in payload.get("problems", [])
        if str(value).strip()
    ]
    after_class_titles = [
        str(value).strip()
        for value in payload.get("afterClassProblems", [])
        if str(value).strip()
    ]
    absent_student_uids = {
        str(value).strip()
        for value in payload.get("absentStudentUids", [])
        if str(value).strip()
    }
    if not group_id:
        raise MatchError("请选择团队")
    if not training_id:
        raise MatchError("请选择训练")
    if not problem_queries:
        raise MatchError("请至少选择一道作业题目" if homework_only else "请至少选择一道课堂题目")

    config = get_config()
    if not config.template_path.exists():
        raise FileNotFoundError(f"模板文件不存在: {config.template_path}")

    team = _find_team(session, group_id)
    training = _find_training(session, group_id, training_id)
    current_problem_payloads = list_problems(session, training_id, training_password)
    current_problems = [_problem_from_payload(item) for item in current_problem_payloads]
    try:
        selected_problems = match_problem_queries(current_problems, problem_queries)
    except MatchError as exc:
        raise MatchError(f"部分课堂题目不在当前训练中，请重新选择: {exc}") from exc

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
    previous_problems = [_problem_from_payload(item) for item in previous_problem_payloads]
    after_class_problems: list[Problem] = []
    for query in after_class_titles:
        try:
            after_class_problems.extend(match_problem_queries(previous_problems, [query]))
        except MatchError:
            continue

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

    report_id = uuid.uuid4().hex
    download_dir = ROOT / ".generated" / report_id
    download_dir.mkdir(parents=True, exist_ok=True)
    request = ReportRequest(
        team_name=team.name,
        training_name=training.title,
        problem_queries=[problem.title for problem in selected_problems],
        template_path=config.template_path,
        output_dir=download_dir,
        after_class_problem_queries=[problem.title for problem in after_class_problems],
        homework_only=homework_only,
    )
    output_path = build_output_path(request)
    rows = build_progress_rows(
        students,
        selected_problems,
        rank_records,
        after_class_problems=[] if homework_only else after_class_problems,
        after_class_rank_records=after_class_rank_records,
        absent_student_uids=set() if homework_only else absent_student_uids,
    )
    render_report(
        request=request,
        problems=selected_problems,
        after_class_problems=[] if homework_only else after_class_problems,
        rows=rows,
        output_path=output_path,
    )
    download_id = uuid.uuid4().hex
    preview = read_report_preview(output_path, len(rows))
    session.reports[report_id] = {"path": output_path, "cells": preview}
    session.downloads[download_id] = output_path
    return {
        "reportId": report_id,
        "title": f"{team.name} · {training.title}",
        "cells": preview,
        "downloadUrl": f"/api/downloads/{download_id}",
        "filename": output_path.name,
    }


def read_report_preview(output_path: Path, student_count: int) -> list[list[dict | None]]:
    workbook = load_workbook(output_path)
    try:
        sheet = workbook.active
        end_row = student_count + 2
        end_col = max(
            (cell.column for row in sheet.iter_rows(max_row=end_row)
             for cell in row if cell.value is not None),
            default=1,
        )
        merged = {item.start_cell.coordinate: item for item in sheet.merged_cells.ranges}
        visible_columns = [
            col for col in range(1, end_col + 1)
            if any(sheet.cell(row, col).value is not None for row in range(1, end_row + 1))
        ] or [1]
        preview = []
        for row_index in range(1, end_row + 1):
            cells = []
            for col in visible_columns:
                cell = sheet.cell(row_index, col)
                if isinstance(cell, MergedCell):
                    cells.append(None)
                    continue
                span = merged.get(cell.coordinate)
                cells.append({
                    "coordinate": cell.coordinate,
                    "value": "" if cell.value is None else str(cell.value),
                    "rowSpan": min(span.max_row, end_row) - cell.row + 1 if span else 1,
                    "colSpan": sum(cell.column <= col <= span.max_col for col in visible_columns) if span else 1,
                    "editable": cell.row >= 3,
                })
            preview.append(cells)
        return preview
    finally:
        workbook.close()


def export_report(session: UserSession, payload: dict) -> dict:
    report = session.reports.get(str(payload.get("reportId") or ""))
    if report is None:
        raise MatchError("学情表已过期，请重新生成。")
    edits = payload.get("edits", {})
    if not isinstance(edits, dict):
        raise MatchError("表格修改内容格式有误。")
    editable = {
        cell["coordinate"] for row in report["cells"]
        for cell in row if cell and cell["editable"]
    }
    for coordinate, value in edits.items():
        if coordinate not in editable:
            raise MatchError("请修改学生数据区域内的单元格。")
        if not isinstance(value, str) or len(value) > 2000:
            raise MatchError("单元格内容须为文本，长度上限为 2000 字。")
        if any(ord(char) < 32 and char not in "\t\n\r" for char in value):
            raise MatchError("单元格内容含有无效字符。")
    workbook = load_workbook(report["path"])
    try:
        sheet = workbook.active
        for coordinate, value in edits.items():
            cell = sheet[coordinate]
            cell.value = value or None
            # 网页输入按文本写入，避免以等号开头的内容成为公式。
            if value:
                cell.data_type = "s"
        download_id = uuid.uuid4().hex
        export_dir = report["path"].parent / download_id
        export_dir.mkdir()
        output_path = export_dir / report["path"].name
        workbook.save(output_path)
    finally:
        workbook.close()
    session.downloads[download_id] = output_path
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
                    session = restore_latest_remembered_session()
                if session is None:
                    self.write_json({"loggedIn": False})
                else:
                    self.write_json(
                        {
                            "loggedIn": True,
                            "account": mask_account(session.account),
                        },
                        cookies=(
                            [self._session_cookie_value(session.session_id, True)]
                            if session.remember
                            else None
                        ),
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
                query = parse_qs(parsed.query)
                search_query = query.get("query", [""])[0]
                limit = int(query.get("limit", ["8"])[0] or 8)
                self.write_json(
                    search_local_problem_bank(
                        ProblemBankSearch(query=search_query, limit=limit)
                    )
                )
                return
            if parsed.path == "/api/agent/tools":
                self.write_json({"tools": AGENT_TOOL_REGISTRY})
                return
            if parsed.path == "/api/agent/runs":
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
            if parsed.path == "/api/reports/export":
                session = self.current_session()
                self.write_json(export_report(session, self.read_json_body()))
                return
            if parsed.path == "/api/students-json":
                session = self.current_session()
                payload = self.read_json_body()
                self.write_json(
                    run_with_oj_retry(session, lambda: save_students(session, payload))
                )
                return
            if parsed.path in ("/api/feedback/summarize-image", "/api/feedback/ocr"):
                payload = self.read_json_body()
                self.write_json(summarize_feedback_image_with_codex(payload))
                return
            if parsed.path == "/api/feedback/check":
                payload = self.read_json_body()
                self.write_json(check_feedback_text_with_codex(payload))
                return
            if parsed.path == "/api/feedback/generate":
                payload = self.read_json_body()
                self.write_json(generate_feedback_with_codex(payload))
                return
            if parsed.path == "/api/feedback/revise":
                payload = self.read_json_body()
                self.write_json(revise_feedback_with_codex(payload))
                return
            if parsed.path == "/api/agent/runs":
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
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def serve_download(self, download_id: str) -> None:
        file_path = self.current_session().downloads.get(download_id)
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
