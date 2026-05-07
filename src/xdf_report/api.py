from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class OJApiError(RuntimeError):
    pass


class _ResponseProtocol(Protocol):
    headers: dict[str, str]

    def raise_for_status(self) -> None:
        ...

    def json(self) -> Any:
        ...


class _SessionProtocol(Protocol):
    headers: dict[str, str]

    def get(self, url: str, **kwargs: Any) -> _ResponseProtocol:
        ...

    def post(self, url: str, **kwargs: Any) -> _ResponseProtocol:
        ...


class _MissingRequestsSession:
    headers: dict[str, str] = {}

    def get(self, *args: Any, **kwargs: Any) -> Any:
        raise OJApiError("requests 库不可用，无法发送 OJ 请求")

    def post(self, *args: Any, **kwargs: Any) -> Any:
        raise OJApiError("requests 库不可用，无法发送 OJ 请求")


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
        raise OJApiError(f"{context} HTTP 错误: {exc}") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise OJApiError(f"{context} 响应解析失败: {exc}") from exc

    if (status := payload.get("status")) is not None and status != 200:
        raise OJApiError(f"{context} 失败: {payload}")
    return payload


def _get(
    session: _SessionProtocol,
    context: str,
    url: str,
    **kwargs: Any,
) -> _ResponseProtocol:
    try:
        return session.get(url, **kwargs)
    except Exception as exc:
        raise OJApiError(f"{context} 请求失败: {exc}") from exc


def _post(
    session: _SessionProtocol,
    context: str,
    url: str,
    **kwargs: Any,
) -> _ResponseProtocol:
    try:
        return session.post(url, **kwargs)
    except Exception as exc:
        raise OJApiError(f"{context} 请求失败: {exc}") from exc


@dataclass
class OJClient:
    token: str
    base_url: str = "https://code.xdf.cn/api/oj"
    _session: _SessionProtocol | None = None

    def __post_init__(self) -> None:
        self.session = _build_session(self._session)
        self.session.headers.update({"Authorization": self.token})

    def get(self, path: str, params: dict) -> dict:
        response = _get(
            self.session,
            f"GET {path}",
            f"{self.base_url}{path}",
            params=params,
            timeout=30,
        )
        return _parse_payload(response, f"GET {path}")

    def post(self, path: str, payload: dict) -> dict:
        response = _post(
            self.session,
            f"POST {path}",
            f"{self.base_url}{path}",
            json=payload,
            timeout=30,
        )
        return _parse_payload(response, f"POST {path}")
