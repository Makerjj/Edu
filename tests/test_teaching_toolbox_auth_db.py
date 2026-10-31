from datetime import timedelta

from teaching_toolbox import server


def test_password_encryption_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "SECRET_KEY_PATH", tmp_path / "secret.key")

    encrypted = server.encrypt_password("oj-password-123")

    assert encrypted != "oj-password-123"
    assert server.decrypt_password(encrypted) == "oj-password-123"


def test_session_restores_from_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "toolbox.sqlite3")
    monkeypatch.setattr(server, "SECRET_KEY_PATH", tmp_path / "secret.key")
    server.state.sessions.clear()

    user_id = server.upsert_user("13800138000", "secret")
    session_id = server.create_session(user_id, "13800138000", "token-value", True)
    server.state.sessions.clear()

    restored = server.restore_session(session_id)

    assert restored is not None
    assert restored.account == "13800138000"
    assert restored.user_id == user_id
    assert session_id in server.state.sessions


def test_session_restore_preserves_remember_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "toolbox.sqlite3")
    monkeypatch.setattr(server, "SECRET_KEY_PATH", tmp_path / "secret.key")
    server.state.sessions.clear()

    user_id = server.upsert_user("13800138000", "secret")
    session_id = server.create_session(user_id, "13800138000", "token-value", True)
    server.state.sessions.clear()

    restored = server.restore_session(session_id)

    assert restored is not None
    assert restored.remember is True


def test_latest_remembered_session_recovers_from_stale_cookie(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "toolbox.sqlite3")
    monkeypatch.setattr(server, "SECRET_KEY_PATH", tmp_path / "secret.key")
    server.state.sessions.clear()

    user_id = server.upsert_user("13800138000", "secret")
    session_id = server.create_session(user_id, "13800138000", "token-value", True)
    server.state.sessions.clear()

    restored = server.restore_latest_remembered_session()

    assert restored is not None
    assert restored.session_id == session_id
    assert restored.account == "13800138000"


def test_expired_session_is_not_restored(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "toolbox.sqlite3")
    monkeypatch.setattr(server, "SECRET_KEY_PATH", tmp_path / "secret.key")
    server.state.sessions.clear()

    user_id = server.upsert_user("13800138000", "secret")
    session_id = server.create_session(user_id, "13800138000", "token-value", True)
    with server.db_connect() as conn:
        conn.execute(
            "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
            (server.utc_iso(server.utc_now() - timedelta(seconds=1)), session_id),
        )
    server.state.sessions.clear()

    assert server.restore_session(session_id) is None


def test_remembered_session_extends_expiry_when_touched(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "toolbox.sqlite3")
    monkeypatch.setattr(server, "SECRET_KEY_PATH", tmp_path / "secret.key")
    server.state.sessions.clear()

    user_id = server.upsert_user("13800138000", "secret")
    session_id = server.create_session(user_id, "13800138000", "token-value", True)
    with server.db_connect() as conn:
        conn.execute(
            "UPDATE sessions SET expires_at = ?, last_seen_at = ? WHERE session_id = ?",
            (
                server.utc_iso(server.utc_now() + timedelta(seconds=10)),
                server.utc_iso(server.utc_now() - timedelta(days=1)),
                session_id,
            ),
        )

    assert server.session_is_valid(session_id) is True

    with server.db_connect() as conn:
        row = conn.execute(
            "SELECT expires_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

    assert server.parse_utc(str(row["expires_at"])) > server.utc_now() + timedelta(days=300)


def test_oj_retry_renews_once(monkeypatch):
    calls = {"operation": 0, "renew": 0}
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=server.OJClient("old-token"),
    )

    def renew(fake_session):
        calls["renew"] += 1
        fake_session.client = server.OJClient("new-token")

    def operation():
        calls["operation"] += 1
        if calls["operation"] == 1:
            raise server.OJApiError("GET /teams 失败: {'status': 401}")
        return session.client.token

    monkeypatch.setattr(server, "renew_session_token", renew)

    assert server.run_with_oj_retry(session, operation) == "new-token"
    assert calls == {"operation": 2, "renew": 1}


def test_renew_session_token_updates_sqlite(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(server, "DB_PATH", tmp_path / "toolbox.sqlite3")
    monkeypatch.setattr(server, "SECRET_KEY_PATH", tmp_path / "secret.key")
    server.state.sessions.clear()

    user_id = server.upsert_user("13800138000", "secret")
    session_id = server.create_session(user_id, "13800138000", "old-token", True)
    session = server.state.sessions[session_id]

    def fetch(account, password):
        assert account == "13800138000"
        assert password == "secret"
        return "new-token"

    monkeypatch.setattr(server, "fetch_oj_token", fetch)

    server.renew_session_token(session)

    assert session.client.token == "new-token"
    with server.db_connect() as conn:
        row = conn.execute(
            "SELECT oj_token FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    assert row["oj_token"] == "new-token"
