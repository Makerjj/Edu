import json
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from openpyxl import load_workbook

from teaching_toolbox import server
from src.xdf_report.models import AppConfig, Student, Team, Training


@pytest.fixture
def report_setup(tmp_path, monkeypatch):
    session = server.UserSession("report-session", 1, "test-account", object())
    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(server, "get_config", lambda: AppConfig(
        None, None, Path("tests/fixtures/template.xlsx"), tmp_path,
    ))
    monkeypatch.setattr(server, "_find_team", lambda *args: Team(1, "测试班"))
    monkeypatch.setattr(server, "_find_training", lambda *args: Training(11, "循环练习"))
    monkeypatch.setattr(server, "list_trainings", lambda *args: [
        {"trainingId": 10, "title": "上周作业"},
        {"trainingId": 11, "title": "循环练习"},
    ])
    monkeypatch.setattr(server, "list_problems", lambda session, training_id, password: [
        {"problemId": "P1001" if training_id == 11 else "P0901",
         "title": "课堂题" if training_id == 11 else "作业题"},
    ])
    monkeypatch.setattr(server, "_load_students", lambda *args: [
        Student("u1", "s1", "学生甲"), Student("u2", "s2", "学生乙"),
    ])
    monkeypatch.setattr(server, "_load_rank_records", lambda client, training_id: [
        {"uid": "u1", "submissionInfo": {
            "P1001" if training_id == 11 else "P0901": {"isAC": True},
        }},
    ])
    payload = {
        "teamId": 1, "trainingId": 11, "problems": ["P1001"],
        "afterClassProblems": ["P0901"], "absentStudentUids": ["u2"],
    }
    return session, payload


def test_preview_uses_exported_headers_and_student_data(report_setup):
    session, payload = report_setup
    result = server.generate_report(session, payload)
    report = session.reports[result["reportId"]]
    cells = result["cells"]
    assert result["title"] == "测试班 · 循环练习"
    assert len(cells) == 4  # 不显示模板内的空学生行。
    assert cells[0][0]["rowSpan"] == 2
    assert cells[1][0] is None
    by_coordinate = {cell["coordinate"]: cell for row in cells for cell in row if cell}
    assert by_coordinate["F2"]["value"] == "课堂题"
    assert by_coordinate["J2"]["value"] == "作业题"
    assert "H3" not in by_coordinate
    assert "I3" not in by_coordinate
    assert cells[2][0]["value"] == "学生甲"
    assert cells[2][5]["value"] == "✅"
    assert cells[3][1]["value"] == "请假"
    assert cells[2][0]["editable"] is True
    assert cells[0][0]["editable"] is False
    workbook = load_workbook(report["path"])
    for row in cells:
        for cell in row:
            if cell:
                value = workbook.active[cell["coordinate"]].value
                assert cell["value"] == ("" if value is None else str(value))
    workbook.close()


def test_homework_only_report_uses_selected_problems_as_homework(report_setup):
    session, payload = report_setup
    payload = {**payload, "homeworkOnly": True, "afterClassProblems": [], "absentStudentUids": ["u1", "u2"]}
    result = server.generate_report(session, payload)
    cells = result["cells"]
    by_coordinate = {cell["coordinate"]: cell for row in cells for cell in row if cell}
    assert by_coordinate["A1"]["value"] == "姓名"
    assert by_coordinate["B1"]["value"] == "本次作业完成情况"
    assert by_coordinate["B2"]["value"] == "课堂题"
    assert "C1" not in by_coordinate
    assert by_coordinate["B3"]["value"] == "✅"
    assert by_coordinate["B4"]["value"] == ""
    assert result["filename"].endswith("课后作业完成情况.xlsx")
    assert all(len(row) == 2 for row in cells)
    values = {cell["value"] for row in cells for cell in row if cell}
    assert values.isdisjoint({"出勤", "课堂表现", "请假", "🌟🌟🌟"})
    download = server.export_report(session, {"reportId": result["reportId"], "edits": {}})
    path = session.downloads[download["downloadUrl"].split("/")[-1]]
    workbook = load_workbook(path)
    try:
        assert workbook.active.max_column == 2
        assert workbook.active["B1"].value == "本次作业完成情况"
    finally:
        workbook.close()


def test_export_preserves_styles_merges_and_edits_without_changing_original(report_setup):
    session, payload = report_setup
    result = server.generate_report(session, payload)
    original = session.reports[result["reportId"]]["path"]
    original_bytes = original.read_bytes()
    edited = {"A3": "学生改名", "C3": "需要提示", "F3": "", "J3": "=1+1"}
    download = server.export_report(session, {"reportId": result["reportId"], "edits": edited})
    path = session.downloads[download["downloadUrl"].split("/")[-1]]
    before = load_workbook(original)
    after = load_workbook(path)
    try:
        assert str(before.active.merged_cells) == str(after.active.merged_cells)
        for coordinate, value in edited.items():
            assert after.active[coordinate].value == (value or None)
            assert after.active[coordinate]._style == before.active[coordinate]._style
        assert after.active["J3"].data_type == "s"
        assert after.active["B4"].value == "请假"
        assert after.active.row_dimensions[3].height == before.active.row_dimensions[3].height
    finally:
        before.close()
        after.close()
    assert original.read_bytes() == original_bytes


@pytest.mark.parametrize("edits", [
    [], {"A1": "改表头"}, {"A5": "模板空行"}, {"XFD3": "越界"},
    {"A3": 2}, {"A3": "字" * 2001}, {"A3": "\x00"},
])
def test_export_rejects_invalid_edits(report_setup, edits):
    session, payload = report_setup
    result = server.generate_report(session, payload)
    with pytest.raises(server.MatchError):
        server.export_report(session, {"reportId": result["reportId"], "edits": edits})


def test_reports_are_isolated_between_requests_and_sessions(report_setup):
    session, payload = report_setup
    first = server.generate_report(session, payload)
    second = server.generate_report(session, payload)
    assert session.reports[first["reportId"]]["path"] != session.reports[second["reportId"]]["path"]
    other = server.UserSession("other-session", 2, "other-account", object())
    with pytest.raises(server.MatchError):
        server.export_report(other, {"reportId": first["reportId"]})


def test_report_http_generation_export_and_authenticated_download(report_setup, monkeypatch):
    session, payload = report_setup
    other = server.UserSession("other-session", 2, "other-account", object())
    sessions = {session.session_id: session, other.session_id: other}
    monkeypatch.setattr(server, "restore_session", lambda sid: sessions.get(sid))
    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.TeachingToolboxHandler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_port}"

    def request(path, data=None, sid=session.session_id):
        headers = {"Cookie": f"{server.COOKIE_NAME}={sid}"} if sid else {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        return urlopen(Request(base + path, data=json.dumps(data).encode() if data is not None else None,
                               headers=headers), timeout=10)

    try:
        with request("/api/reports", payload) as response:
            result = json.load(response)
        with request("/api/reports/export", {"reportId": result["reportId"], "edits": {"C3": "修改"}}) as response:
            download = json.load(response)
        with request(download["downloadUrl"]) as response:
            assert response.status == 200
            assert response.headers["Content-Disposition"].startswith("attachment;")
            assert response.read().startswith(b"PK")
        for sid, status in [(None, 401), (other.session_id, 404)]:
            with pytest.raises(HTTPError) as error:
                request(download["downloadUrl"], sid=sid)
            assert error.value.code == status
        with pytest.raises(HTTPError) as error:
            request("/api/reports/export", {"reportId": result["reportId"]}, sid=None)
        assert error.value.code == 401
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
