import json
from pathlib import Path

from src.xdf_report.api import OJApiError
from src.xdf_report.cli import (
    _sort_students_by_name,
    build_output_path,
    build_parser,
    extract_group_id_from_query,
    main,
    parse_problem_queries,
    resolve_team,
)
from src.xdf_report.models import AppConfig, ReportRequest
from src.xdf_report.models import Student


def _make_request(tmp_path: Path, problem_queries: list[str]) -> ReportRequest:
    return ReportRequest(
        team_name="易生活102 C1",
        training_name="二分查找",
        problem_queries=problem_queries,
        template_path=Path("tests/fixtures/template.xlsx"),
        output_dir=tmp_path,
    )


def test_build_parser_reads_required_arguments() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果,字典找字,查找",
        ]
    )

    assert args.team == "易生活102 C1"
    assert args.training == "二分查找"
    assert args.problems == "找苹果,字典找字,查找"


def test_build_parser_reads_optional_after_class_problems() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果",
            "--after-class-problems",
            "复习题1,复习题2",
        ]
    )

    assert args.after_class_problems == "复习题1,复习题2"


def test_parse_problem_queries_splits_and_trims_values() -> None:
    assert parse_problem_queries(" 找苹果, 字典找字 , ,查找 ") == [
        "找苹果",
        "字典找字",
        "查找",
    ]


def test_load_students_from_json_file_respects_name_order(tmp_path: Path, monkeypatch) -> None:
    from src.xdf_report.cli import _load_students_from_json

    json_path = tmp_path / "students.json"
    json_path.write_text(
        json.dumps(
            {
                "students": [
                    {
                        "uid": "u2",
                        "username": "s2",
                        "nickname": "学生B",
                        "real_name": "学生B",
                    },
                    {
                        "uid": "u1",
                        "username": "s1",
                        "nickname": "学生A",
                        "real_name": "学生A",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    students = _load_students_from_json(json_path)

    assert [student.uid for student in students] == ["u1", "u2"]
    assert [student.nickname for student in students] == ["学生A", "学生B"]


def test_sort_students_by_name_uses_chinese_pinyin_and_places_non_chinese_last() -> None:
    students = [
        Student(uid="u4", username="s4", nickname="QTZB1636010762"),
        Student(uid="u3", username="s3", nickname="张三"),
        Student(uid="u2", username="s2", nickname="王五"),
        Student(uid="u1", username="s1", nickname="李四"),
    ]

    sorted_students = _sort_students_by_name(students)

    assert [student.nickname for student in sorted_students] == [
        "李四",
        "王五",
        "张三",
        "QTZB1636010762",
    ]


def test_build_output_path_uses_short_name_for_multiple_problems(tmp_path: Path) -> None:
    request = _make_request(tmp_path, ["找苹果", "字典找字", "查找"])

    output_path = build_output_path(request)

    assert output_path == tmp_path / "易生活102 C1_二分查找_找苹果等3题_学情反馈表.xlsx"


def test_main_uses_students_json_to_filter_and_sort_users(
    tmp_path: Path, monkeypatch
) -> None:
    rendered: dict[str, object] = {}
    student_ids: list[str] = []

    json_path = tmp_path / "students.json"
    json_path.write_text(
        json.dumps(
            {
                "students": [
                    {
                        "uid": "u2",
                        "username": "s2",
                        "nickname": "学生B",
                        "real_name": "学生B",
                    },
                    {
                        "uid": "u1",
                        "username": "s1",
                        "nickname": "学生A",
                        "real_name": "学生A",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class FakeAuthClient:
        def login(self, account: str, password: str) -> str:
            return "dd-token"

        def get_students(self, token: str) -> list[dict]:
            return [{"studentCode": "S001"}]

        def login_oj(self, token: str, student_code: str):
            return type("Session", (), {"oj_token": "oj-token"})()

    class FakeOJClient:
        def __init__(self, token: str) -> None:
            assert token == "oj-token"

        def get(self, path: str, params: dict) -> dict:
            if path == "/get-group-list":
                return {"data": {"records": [{"id": 1, "name": "易生活102 C1"}]}}
            if path == "/group/get-training-list":
                return {"data": {"records": [{"id": 11, "title": "二分查找"}]}}
            if path == "/get-training-problem-list":
                return {"data": [{"problemId": "P1001", "title": "找苹果"}]}
            if path == "/get-training-rank":
                return {"data": {"records": [{"uid": "u1", "submissionInfo": {"P1001": {"isAC": True}}}, {"uid": "u2", "submissionInfo": {"P1001": {"isAC": False}}}]}}
            raise AssertionError(path)

    def fake_build_progress_rows(students, problems, rank_records, after_class_problems=None, after_class_rank_records=None):
        student_ids.extend([student.uid for student in students])
        rendered["rows"] = []
        return []

    def fake_render_report(request, problems, after_class_problems, rows, output_path: Path) -> None:
        rendered["request"] = request
        rendered["output_path"] = output_path

    monkeypatch.setattr(
        "src.xdf_report.cli.load_config",
        lambda path: AppConfig(
            account="19951913492",
            password="qwe123456",
            template_path=Path("tests/fixtures/template.xlsx"),
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr("src.xdf_report.cli.ensure_credentials", lambda config: config)
    monkeypatch.setattr("src.xdf_report.cli.DingdangAuthClient", FakeAuthClient)
    monkeypatch.setattr("src.xdf_report.cli.OJClient", FakeOJClient)
    monkeypatch.setattr("src.xdf_report.cli.build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr("src.xdf_report.cli.render_report", fake_render_report)

    exit_code = main(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果",
            "--students-json",
            str(json_path),
        ]
    )

    assert exit_code == 0
    assert student_ids == ["u1", "u2"]
    assert rendered["output_path"] == tmp_path / "易生活102 C1_二分查找_找苹果_学情反馈表.xlsx"


def test_main_ignores_default_students_json_when_not_explicit(
    tmp_path: Path, monkeypatch
) -> None:
    rendered: dict[str, object] = {}
    student_ids: list[str] = []

    default_json_path = tmp_path / "students.c1-3.json"
    default_json_path.write_text(
        json.dumps(
            {
                "students": [
                    {
                        "uid": "u2",
                        "username": "s2",
                        "nickname": "学生B",
                        "real_name": "学生B",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class FakeAuthClient:
        def login(self, account: str, password: str) -> str:
            return "dd-token"

        def get_students(self, token: str) -> list[dict]:
            return [{"studentCode": "S001"}]

        def login_oj(self, token: str, student_code: str):
            return type("Session", (), {"oj_token": "oj-token"})()

    class FakeOJClient:
        def __init__(self, token: str) -> None:
            assert token == "oj-token"

        def get(self, path: str, params: dict) -> dict:
            if path == "/get-group-list":
                return {"data": {"records": [{"id": 1, "name": "易生活102 C1"}]}}
            if path == "/group/get-training-list":
                return {"data": {"records": [{"id": 11, "title": "二分查找"}]}}
            if path == "/get-training-problem-list":
                return {"data": [{"problemId": "P1001", "title": "找苹果"}]}
            if path == "/group/get-member-list":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u1",
                                "username": "s1",
                                "nickname": "学生A",
                                "auth": 3,
                            }
                        ]
                    }
                }
            if path == "/get-training-rank":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u1",
                                "submissionInfo": {"P1001": {"isAC": True}},
                            }
                        ]
                    }
                }
            raise AssertionError(path)

    def fake_build_progress_rows(students, problems, rank_records, after_class_problems=None, after_class_rank_records=None):
        student_ids.extend([student.uid for student in students])
        return []

    def fake_render_report(request, problems, after_class_problems, rows, output_path: Path) -> None:
        rendered["output_path"] = output_path

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "src.xdf_report.cli.load_config",
        lambda path: AppConfig(
            account="19951913492",
            password="qwe123456",
            template_path=Path(__file__).resolve().parent / "fixtures/template.xlsx",
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr("src.xdf_report.cli.ensure_credentials", lambda config: config)
    monkeypatch.setattr("src.xdf_report.cli.DingdangAuthClient", FakeAuthClient)
    monkeypatch.setattr("src.xdf_report.cli.OJClient", FakeOJClient)
    monkeypatch.setattr("src.xdf_report.cli.build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr("src.xdf_report.cli.render_report", fake_render_report)

    exit_code = main(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果",
        ]
    )

    assert exit_code == 0
    assert student_ids == ["u1"]
    assert rendered["output_path"] == tmp_path / "易生活102 C1_二分查找_找苹果_学情反馈表.xlsx"


def test_main_sorts_api_loaded_students_by_name(
    tmp_path: Path, monkeypatch
) -> None:
    student_ids: list[str] = []

    class FakeAuthClient:
        def login(self, account: str, password: str) -> str:
            return "dd-token"

        def get_students(self, token: str) -> list[dict]:
            return [{"studentCode": "S001"}]

        def login_oj(self, token: str, student_code: str):
            return type("Session", (), {"oj_token": "oj-token"})()

    class FakeOJClient:
        def __init__(self, token: str) -> None:
            assert token == "oj-token"

        def get(self, path: str, params: dict) -> dict:
            if path == "/get-group-list":
                return {"data": {"records": [{"id": 1, "name": "易生活102 C1"}]}}
            if path == "/group/get-training-list":
                return {"data": {"records": [{"id": 11, "title": "二分查找"}]}}
            if path == "/get-training-problem-list":
                return {"data": [{"problemId": "P1001", "title": "找苹果"}]}
            if path == "/group/get-member-list":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u2",
                                "username": "s2",
                                "nickname": "学生B",
                                "auth": 3,
                            },
                            {
                                "uid": "u1",
                                "username": "s1",
                                "nickname": "学生A",
                                "auth": 3,
                            },
                        ]
                    }
                }
            if path == "/get-training-rank":
                return {
                    "data": {
                        "records": [
                            {"uid": "u1", "submissionInfo": {"P1001": {"isAC": True}}},
                            {"uid": "u2", "submissionInfo": {"P1001": {"isAC": False}}},
                        ]
                    }
                }
            raise AssertionError(path)

    def fake_build_progress_rows(
        students, problems, rank_records, after_class_problems=None, after_class_rank_records=None
    ):
        student_ids.extend([student.uid for student in students])
        return []

    monkeypatch.setattr(
        "src.xdf_report.cli.load_config",
        lambda path: AppConfig(
            account="19951913492",
            password="qwe123456",
            template_path=Path("tests/fixtures/template.xlsx"),
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr("src.xdf_report.cli.ensure_credentials", lambda config: config)
    monkeypatch.setattr("src.xdf_report.cli.DingdangAuthClient", FakeAuthClient)
    monkeypatch.setattr("src.xdf_report.cli.OJClient", FakeOJClient)
    monkeypatch.setattr("src.xdf_report.cli.build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr(
        "src.xdf_report.cli.render_report",
        lambda request, problems, after_class_problems, rows, output_path: None,
    )

    exit_code = main(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果",
        ]
    )

    assert exit_code == 0
    assert student_ids == ["u1", "u2"]


def test_extract_group_id_from_query_supports_plain_id_and_group_url() -> None:
    assert extract_group_id_from_query("2186") == 2186
    assert extract_group_id_from_query("https://code.xdf.cn/oj/group/2186") == 2186
    assert extract_group_id_from_query("易生活102 C1") is None


def test_resolve_team_falls_back_to_group_detail_scan_when_group_list_fails() -> None:
    class FakeOJClient:
        def get(self, path: str, params: dict) -> dict:
            if path == "/get-group-list":
                raise OJApiError("Server Error")
            if path == "/get-group-detail":
                gid = params["gid"]
                if gid == 3:
                    return {"status": 200, "data": {"id": 3, "name": "易生活102 C1"}}
                return {"status": 404, "data": None, "msg": "not found"}
            if path == "/group/get-training-list":
                if params["gid"] == 3:
                    return {"status": 200, "data": {"records": []}}
                return {"status": 403, "data": None, "msg": "forbidden"}
            raise AssertionError(path)

    team = resolve_team(FakeOJClient(), "易生活102 C1", scan_max_id=5, scan_workers=2)

    assert team.group_id == 3
    assert team.name == "易生活102 C1"


def test_main_generates_report_with_fake_clients(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    rendered: dict[str, object] = {}

    class FakeAuthClient:
        def login(self, account: str, password: str) -> str:
            assert account == "19951913492"
            assert password == "qwe123456"
            return "dd-token"

        def get_students(self, token: str) -> list[dict]:
            assert token == "dd-token"
            return [{"studentCode": "S001"}]

        def login_oj(self, token: str, student_code: str):
            assert token == "dd-token"
            assert student_code == "S001"
            return type("Session", (), {"oj_token": "oj-token"})()

    class FakeOJClient:
        def __init__(self, token: str) -> None:
            assert token == "oj-token"

        def get(self, path: str, params: dict) -> dict:
            if path == "/get-group-list":
                return {"data": {"records": [{"id": 1, "name": "易生活102 C1"}]}}
            if path == "/group/get-training-list":
                return {"data": {"records": [{"id": 11, "title": "二分查找"}]}}
            if path == "/get-training-problem-list":
                return {
                    "data": [
                        {"problemId": "P1001", "title": "找苹果"},
                        {"problemId": "P1002", "title": "字典找字"},
                    ]
                }
            if path == "/group/get-member-list":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u1",
                                "username": "s1",
                                "nickname": "学生1",
                                "auth": 3,
                            }
                        ]
                    }
                }
            if path == "/get-training-rank":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u1",
                                "submissionInfo": {"P1001": {"isAC": True}},
                            }
                        ]
                    }
                }
            raise AssertionError(path)

    def fake_render_report(
        request, problems, after_class_problems, rows, output_path: Path
    ) -> None:
        rendered["request"] = request
        rendered["problems"] = problems
        rendered["after_class_problems"] = after_class_problems
        rendered["rows"] = rows
        rendered["output_path"] = output_path

    monkeypatch.setattr(
        "src.xdf_report.cli.load_config",
        lambda path: AppConfig(
            account="19951913492",
            password="qwe123456",
            template_path=Path("tests/fixtures/template.xlsx"),
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr("src.xdf_report.cli.ensure_credentials", lambda config: config)
    monkeypatch.setattr("src.xdf_report.cli.DingdangAuthClient", FakeAuthClient)
    monkeypatch.setattr("src.xdf_report.cli.OJClient", FakeOJClient)
    monkeypatch.setattr("src.xdf_report.cli.render_report", fake_render_report)

    exit_code = main(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果",
        ]
    )

    assert exit_code == 0
    assert rendered["output_path"] == tmp_path / "易生活102 C1_二分查找_找苹果_学情反馈表.xlsx"
    assert rendered["after_class_problems"] == []
    assert capsys.readouterr().out.strip() == str(rendered["output_path"])


def test_main_registers_private_training_before_loading_problems(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    rendered: dict[str, object] = {}

    class FakeAuthClient:
        def login(self, account: str, password: str) -> str:
            return "dd-token"

        def get_students(self, token: str) -> list[dict]:
            return [{"studentCode": "S001"}]

        def login_oj(self, token: str, student_code: str):
            return type("Session", (), {"oj_token": "oj-token"})()

    class FakeOJClient:
        def __init__(self, token: str) -> None:
            self.training_registered = False

        def get(self, path: str, params: dict) -> dict:
            if path == "/get-group-list":
                return {"data": {"records": [{"id": 1, "name": "易生活102 C1"}]}}
            if path == "/group/get-training-list":
                return {"data": {"records": [{"id": 11, "title": "二分查找"}]}}
            if path == "/get-training-problem-list":
                if not self.training_registered:
                    raise OJApiError(
                        "GET /get-training-problem-list 失败: {'status': 401, 'data': None, 'msg': '该训练属于私有，请先使用专属密码注册！'}"
                    )
                return {"data": [{"problemId": "P1001", "title": "找苹果"}]}
            if path == "/group/get-member-list":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u1",
                                "username": "s1",
                                "nickname": "学生1",
                                "auth": 3,
                            }
                        ]
                    }
                }
            if path == "/get-training-rank":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u1",
                                "submissionInfo": {"P1001": {"isAC": True}},
                            }
                        ]
                    }
                }
            raise AssertionError(path)

        def post(self, path: str, payload: dict) -> dict:
            if path == "/register-training":
                assert payload == {"tid": 11, "password": "1"}
                self.training_registered = True
                return {"status": 200, "data": None, "msg": "success"}
            raise AssertionError(path)

    def fake_render_report(
        request, problems, after_class_problems, rows, output_path: Path
    ) -> None:
        rendered["after_class_problems"] = after_class_problems
        rendered["output_path"] = output_path

    monkeypatch.setattr(
        "src.xdf_report.cli.load_config",
        lambda path: AppConfig(
            account="19951913492",
            password="qwe123456",
            template_path=Path("tests/fixtures/template.xlsx"),
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr("src.xdf_report.cli.ensure_credentials", lambda config: config)
    monkeypatch.setattr("src.xdf_report.cli.DingdangAuthClient", FakeAuthClient)
    monkeypatch.setattr("src.xdf_report.cli.OJClient", FakeOJClient)
    monkeypatch.setattr("src.xdf_report.cli.render_report", fake_render_report)

    exit_code = main(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果",
            "--training-password",
            "1",
        ]
    )

    assert exit_code == 0
    assert rendered["output_path"] == tmp_path / "易生活102 C1_二分查找_找苹果_学情反馈表.xlsx"
    assert rendered["after_class_problems"] == []
    assert capsys.readouterr().out.strip() == str(rendered["output_path"])


def test_main_warns_and_skips_unmatched_after_class_problem(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    rendered: dict[str, object] = {}
    progress_call: dict[str, object] = {}

    class FakeAuthClient:
        def login(self, account: str, password: str) -> str:
            return "dd-token"

        def get_students(self, token: str) -> list[dict]:
            return [{"studentCode": "S001"}]

        def login_oj(self, token: str, student_code: str):
            return type("Session", (), {"oj_token": "oj-token"})()

    class FakeOJClient:
        def __init__(self, token: str) -> None:
            assert token == "oj-token"

        def get(self, path: str, params: dict) -> dict:
            if path == "/get-group-list":
                return {"data": {"records": [{"id": 1, "name": "易生活102 C1"}]}}
            if path == "/group/get-training-list":
                return {
                    "data": {
                        "records": [
                            {"id": 10, "title": "前序训练"},
                            {"id": 11, "title": "二分查找"},
                        ]
                    }
                }
            if path == "/get-training-problem-list":
                if params["tid"] == 11:
                    return {"data": [{"problemId": "P1001", "title": "找苹果"}]}
                if params["tid"] == 10:
                    return {"data": [{"problemId": "P0901", "title": "旧题"}]}
            if path == "/group/get-member-list":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u1",
                                "username": "s1",
                                "nickname": "学生1",
                                "auth": 3,
                            }
                        ]
                    }
                }
            if path == "/get-training-rank":
                return {"data": {"records": [{"uid": "u1", "submissionInfo": {}}]}}
            raise AssertionError(path)

    def fake_build_progress_rows(
        students, problems, rank_records, after_class_problems=None, after_class_rank_records=None
    ):
        progress_call["students"] = students
        progress_call["problems"] = problems
        progress_call["rank_records"] = rank_records
        progress_call["after_class_problems"] = after_class_problems
        progress_call["after_class_rank_records"] = after_class_rank_records
        return ["row"]

    def fake_render_report(
        request, problems, after_class_problems, rows, output_path: Path
    ) -> None:
        rendered["request"] = request
        rendered["problems"] = problems
        rendered["after_class_problems"] = after_class_problems
        rendered["rows"] = rows
        rendered["output_path"] = output_path

    monkeypatch.setattr(
        "src.xdf_report.cli.load_config",
        lambda path: AppConfig(
            account="19951913492",
            password="qwe123456",
            template_path=Path("tests/fixtures/template.xlsx"),
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr("src.xdf_report.cli.ensure_credentials", lambda config: config)
    monkeypatch.setattr("src.xdf_report.cli.DingdangAuthClient", FakeAuthClient)
    monkeypatch.setattr("src.xdf_report.cli.OJClient", FakeOJClient)
    monkeypatch.setattr("src.xdf_report.cli.build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr("src.xdf_report.cli.render_report", fake_render_report)

    exit_code = main(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果",
            "--after-class-problems",
            "不存在的题目",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert rendered["rows"] == ["row"]
    assert rendered["request"].after_class_problem_queries == []
    assert rendered["after_class_problems"] == []
    assert progress_call["after_class_problems"] == []
    assert progress_call["after_class_rank_records"] == []
    assert "不存在的题目" in captured.err
    assert "当前训练未匹配" in captured.err
    assert "上一训练未匹配" in captured.err


def test_main_falls_back_to_previous_training_for_after_class_problem(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    rendered: dict[str, object] = {}
    progress_call: dict[str, object] = {}

    class FakeAuthClient:
        def login(self, account: str, password: str) -> str:
            return "dd-token"

        def get_students(self, token: str) -> list[dict]:
            return [{"studentCode": "S001"}]

        def login_oj(self, token: str, student_code: str):
            return type("Session", (), {"oj_token": "oj-token"})()

    class FakeOJClient:
        def __init__(self, token: str) -> None:
            assert token == "oj-token"

        def get(self, path: str, params: dict) -> dict:
            if path == "/get-group-list":
                return {"data": {"records": [{"id": 1, "name": "易生活102 C1"}]}}
            if path == "/group/get-training-list":
                return {
                    "data": {
                        "records": [
                            {"id": 10, "title": "前序训练"},
                            {"id": 11, "title": "二分查找"},
                        ]
                    }
                }
            if path == "/get-training-problem-list":
                if params["tid"] == 11:
                    return {"data": [{"problemId": "P1001", "title": "找苹果"}]}
                if params["tid"] == 10:
                    return {"data": [{"problemId": "P0901", "title": "课后巩固"}]}
            if path == "/group/get-member-list":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u1",
                                "username": "s1",
                                "nickname": "学生1",
                                "auth": 3,
                            }
                        ]
                    }
                }
            if path == "/get-training-rank":
                if params["tid"] == 11:
                    return {
                        "data": {
                            "records": [{"uid": "u1", "submissionInfo": {"P1001": {"isAC": True}}}]
                        }
                    }
                if params["tid"] == 10:
                    return {
                        "data": {
                            "records": [{"uid": "u1", "submissionInfo": {"P0901": {"isAC": True}}}]
                        }
                    }
            raise AssertionError(path)

    def fake_build_progress_rows(
        students, problems, rank_records, after_class_problems=None, after_class_rank_records=None
    ):
        progress_call["students"] = students
        progress_call["problems"] = problems
        progress_call["rank_records"] = rank_records
        progress_call["after_class_problems"] = after_class_problems
        progress_call["after_class_rank_records"] = after_class_rank_records
        return ["row"]

    def fake_render_report(
        request, problems, after_class_problems, rows, output_path: Path
    ) -> None:
        rendered["request"] = request
        rendered["problems"] = problems
        rendered["after_class_problems"] = after_class_problems
        rendered["rows"] = rows
        rendered["output_path"] = output_path

    monkeypatch.setattr(
        "src.xdf_report.cli.load_config",
        lambda path: AppConfig(
            account="19951913492",
            password="qwe123456",
            template_path=Path("tests/fixtures/template.xlsx"),
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr("src.xdf_report.cli.ensure_credentials", lambda config: config)
    monkeypatch.setattr("src.xdf_report.cli.DingdangAuthClient", FakeAuthClient)
    monkeypatch.setattr("src.xdf_report.cli.OJClient", FakeOJClient)
    monkeypatch.setattr("src.xdf_report.cli.build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr("src.xdf_report.cli.render_report", fake_render_report)

    exit_code = main(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果",
            "--after-class-problems",
            "课后巩固",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert rendered["request"].after_class_problem_queries == ["课后巩固"]
    assert [problem.title for problem in rendered["after_class_problems"]] == ["课后巩固"]
    assert [problem.title for problem in progress_call["after_class_problems"]] == ["课后巩固"]
    assert progress_call["after_class_rank_records"] == [
        {"uid": "u1", "submissionInfo": {"P0901": {"isAC": True}}}
    ]


def test_main_merges_after_class_rank_records_for_mixed_sources(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    progress_call: dict[str, object] = {}

    class FakeAuthClient:
        def login(self, account: str, password: str) -> str:
            return "dd-token"

        def get_students(self, token: str) -> list[dict]:
            return [{"studentCode": "S001"}]

        def login_oj(self, token: str, student_code: str):
            return type("Session", (), {"oj_token": "oj-token"})()

    class FakeOJClient:
        def __init__(self, token: str) -> None:
            assert token == "oj-token"

        def get(self, path: str, params: dict) -> dict:
            if path == "/get-group-list":
                return {"data": {"records": [{"id": 1, "name": "易生活102 C1"}]}}
            if path == "/group/get-training-list":
                return {
                    "data": {
                        "records": [
                            {"id": 10, "title": "前序训练"},
                            {"id": 11, "title": "二分查找"},
                        ]
                    }
                }
            if path == "/get-training-problem-list":
                if params["tid"] == 11:
                    return {
                        "data": [
                            {"problemId": "P1001", "title": "找苹果"},
                            {"problemId": "P1002", "title": "当前课后题"},
                        ]
                    }
                if params["tid"] == 10:
                    return {"data": [{"problemId": "P0901", "title": "上一课后题"}]}
            if path == "/group/get-member-list":
                return {
                    "data": {
                        "records": [
                            {
                                "uid": "u1",
                                "username": "s1",
                                "nickname": "学生1",
                                "auth": 3,
                            }
                        ]
                    }
                }
            if path == "/get-training-rank":
                if params["tid"] == 11:
                    return {
                        "data": {
                            "records": [
                                {
                                    "uid": "u1",
                                    "rank": 1,
                                    "solvedCount": 2,
                                    "submissionInfo": {
                                        "P1001": {"isAC": True},
                                        "P1002": {"isAC": True},
                                    },
                                }
                            ]
                        }
                    }
                if params["tid"] == 10:
                    return {
                        "data": {
                            "records": [
                                {
                                    "uid": "u1",
                                    "rank": 99,
                                    "solvedCount": 1,
                                    "submissionInfo": {"P0901": {"isAC": True}},
                                }
                            ]
                        }
                    }
            raise AssertionError(path)

    def fake_build_progress_rows(
        students, problems, rank_records, after_class_problems=None, after_class_rank_records=None
    ):
        progress_call["after_class_problems"] = after_class_problems
        progress_call["after_class_rank_records"] = after_class_rank_records
        return ["row"]

    monkeypatch.setattr(
        "src.xdf_report.cli.load_config",
        lambda path: AppConfig(
            account="19951913492",
            password="qwe123456",
            template_path=Path("tests/fixtures/template.xlsx"),
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr("src.xdf_report.cli.ensure_credentials", lambda config: config)
    monkeypatch.setattr("src.xdf_report.cli.DingdangAuthClient", FakeAuthClient)
    monkeypatch.setattr("src.xdf_report.cli.OJClient", FakeOJClient)
    monkeypatch.setattr("src.xdf_report.cli.build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr("src.xdf_report.cli.render_report", lambda *args, **kwargs: None)

    exit_code = main(
        [
            "--team",
            "易生活102 C1",
            "--training",
            "二分查找",
            "--problems",
            "找苹果",
            "--after-class-problems",
            "当前课后题,上一课后题",
        ]
    )

    captured = capsys.readouterr()
    merged_records = progress_call["after_class_rank_records"]

    assert exit_code == 0
    assert captured.err == ""
    assert [problem.title for problem in progress_call["after_class_problems"]] == [
        "当前课后题",
        "上一课后题",
    ]
    assert merged_records == [
        {
            "uid": "u1",
            "rank": 1,
            "solvedCount": 2,
            "submissionInfo": {
                "P1001": {"isAC": True},
                "P1002": {"isAC": True},
                "P0901": {"isAC": True},
            },
        }
    ]
