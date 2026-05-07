from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class AuthError(RuntimeError):
    pass


@dataclass
class AuthSession:
    oj_token: str
    student_code: str


class _ResponseProtocol(Protocol):
    headers: dict[str, str]

    def raise_for_status(self) -> None:
        ...

    def json(self) -> Any:
        ...


class _SessionProtocol(Protocol):
    headers: dict[str, str]

    def post(self, url: str, **kwargs: Any) -> _ResponseProtocol:
        ...


class _MissingRequestsSession:
    headers: dict[str, str] = {}

    def post(self, *args: Any, **kwargs: Any) -> Any:
        raise AuthError("requests 库不可用，无法进行登录请求")


def _build_session(session: _SessionProtocol | None) -> _SessionProtocol:
    if session is not None:
        return session

    try:
        import requests
    except ModuleNotFoundError:  # pragma: no cover
        return _MissingRequestsSession()

    return requests.Session()


def _parse_payload(response: _ResponseProtocol, context: str) -> dict[str, Any]:
    try:
        response.raise_for_status()
    except Exception as exc:
        raise AuthError(f"{context} HTTP 错误: {exc}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise AuthError(f"{context} 响应解析失败: {exc}") from exc

    status = payload.get("status")
    if status is not None and status != 200:
        raise AuthError(f"{context} 失败: {payload}")
    return payload


def _post(
    session: _SessionProtocol,
    context: str,
    url: str,
    **kwargs: Any,
) -> _ResponseProtocol:
    try:
        return session.post(url, **kwargs)
    except Exception as exc:
        raise AuthError(f"{context} 请求失败: {exc}") from exc


class DingdangAuthClient:
    dd_base_url = "https://code.xdf.cn/api/dingdang"
    oj_base_url = "https://code.xdf.cn/api/oj"

    def __init__(self, session: "_SessionProtocol | None" = None) -> None:
        self.session = _build_session(session)

    def login(self, account: str, password: str) -> str:
        response = _post(
            self.session,
            "登录钉钉",
            f"{self.dd_base_url}/account/login",
            json={"account": account, "password": password},
            timeout=30,
        )
        data = _parse_payload(response, "登录钉钉")
        token = data.get("data", {}).get("token")
        if not token:
            raise AuthError(f"登录失败: {data}")
        return token

    def get_students(self, token: str) -> list[dict]:
        response = _post(
            self.session,
            "获取学生列表",
            f"{self.oj_base_url}/getStudents",
            json={"token": token},
            timeout=30,
        )
        data = _parse_payload(response, "获取学生列表")
        return data.get("data", [])

    def login_oj(self, token: str, student_code: str) -> AuthSession:
        response = _post(
            self.session,
            "登录 OJ",
            f"{self.oj_base_url}/loginByToken",
            json={"token": token, "studentCode": student_code},
            timeout=30,
        )
        _parse_payload(response, "登录 OJ")
        oj_token = response.headers.get("Authorization")
        if not oj_token:
            raise AuthError("未获取到 OJ Authorization")
        return AuthSession(oj_token=oj_token, student_code=student_code)
