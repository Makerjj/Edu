import json

from openpyxl import Workbook

from teaching_toolbox import server
from src.xdf_report.models import AppConfig, Student, Training


def test_list_teams_uses_official_group_list_before_scan(monkeypatch):
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
    )

    monkeypatch.setattr(
        server,
        "_load_teams",
        lambda client, keyword: [
            type("Team", (), {"group_id": 2829, "name": "测试团队"})(),
        ],
    )

    def fail_scan(*args):
        raise AssertionError("不应在官方团队列表可用时扫描 gid")

    monkeypatch.setattr(server, "_scan_teams_by_name", fail_scan)

    assert server.list_teams(session) == [{"groupId": 2829, "name": "测试团队"}]


def test_list_teams_renews_token_when_official_group_list_is_empty(monkeypatch):
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
    )
    calls = {"load": 0, "renew": 0}

    def fake_load_teams(client, keyword):
        calls["load"] += 1
        if calls["load"] == 1:
            return []
        return [type("Team", (), {"group_id": 2829, "name": "测试团队"})()]

    def fake_renew(fake_session):
        calls["renew"] += 1

    monkeypatch.setattr(server, "_load_teams", fake_load_teams)
    monkeypatch.setattr(server, "renew_session_token", fake_renew)

    assert server.list_teams(session) == [{"groupId": 2829, "name": "测试团队"}]
    assert calls == {"load": 2, "renew": 1}


def test_list_teams_renews_token_when_official_group_list_errors(monkeypatch):
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
    )
    calls = {"load": 0, "renew": 0}

    def fake_load_teams(client, keyword):
        calls["load"] += 1
        if calls["load"] == 1:
            raise server.OJApiError("GET /get-group-list HTTP 错误: 500")
        return [type("Team", (), {"group_id": 2829, "name": "测试团队"})()]

    def fake_renew(fake_session):
        calls["renew"] += 1

    def fail_scan(*args):
        raise AssertionError("应先续期重试官方团队列表")

    monkeypatch.setattr(server, "_load_teams", fake_load_teams)
    monkeypatch.setattr(server, "renew_session_token", fake_renew)
    monkeypatch.setattr(server, "_scan_teams_by_name", fail_scan)

    assert server.list_teams(session) == [{"groupId": 2829, "name": "测试团队"}]
    assert calls == {"load": 2, "renew": 1}


def test_list_trainings_reloads_each_time_to_include_new_training(monkeypatch):
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
    )
    calls = {"load": 0}

    def fake_load_trainings(client, group_id):
        calls["load"] += 1
        if calls["load"] == 1:
            return [Training(training_id=1, title="旧训练")]
        return [
            Training(training_id=1, title="旧训练"),
            Training(training_id=2, title="埃氏法"),
        ]

    monkeypatch.setattr(server, "_load_trainings", fake_load_trainings)

    assert server.list_trainings(session, 1949) == [
        {"trainingId": 1, "title": "旧训练"}
    ]
    assert server.list_trainings(session, 1949) == [
        {"trainingId": 1, "title": "旧训练"},
        {"trainingId": 2, "title": "埃氏法"},
    ]
    assert calls == {"load": 2}


def test_save_students_writes_selected_students_with_edited_real_name(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        server,
        "_find_team",
        lambda session, group_id: type("Team", (), {"group_id": group_id, "name": "测试班"})(),
    )

    result = server.save_students(
        object(),
        {
            "teamId": 2186,
            "filename": "students.test.json",
            "students": [
                {
                    "uid": "u1",
                    "username": "SZS001",
                    "nickname": "Jason 褚亮",
                    "realName": "褚亮",
                    "school": "苏州高新区实验初级中学",
                    "phone": "13800138000",
                },
                {
                    "uid": "u2",
                    "username": "SZS002",
                    "nickname": "庞雅心",
                    "realName": "庞雅心",
                },
            ],
        }
    )

    output_path = tmp_path / "students.test.json"
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert result == {"path": str(output_path), "count": 2}
    assert payload["team_gid"] == 2186
    assert payload["team_name"] == "测试班"
    assert payload["students"][0] == {
        "uid": "u1",
        "username": "SZS001",
        "nickname": "Jason 褚亮",
        "real_name": "褚亮",
        "school": "苏州高新区实验初级中学",
        "phone": "13800138000",
    }


def test_list_saved_students_reads_saved_real_name(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    path = tmp_path / "students.2186.json"
    path.write_text(
        json.dumps(
            {
                "team_gid": 2186,
                "team_name": "测试班",
                "students": [
                    {
                        "uid": "u1",
                        "username": "SZS001",
                        "nickname": "Jason 褚亮",
                        "real_name": "褚亮",
                        "school": "苏州高新区实验初级中学",
                        "phone": "13800138000",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = server.list_saved_students(2186)

    assert result["exists"] is True
    assert result["count"] == 1
    assert result["students"][0] == {
        "uid": "u1",
        "username": "SZS001",
        "nickname": "Jason 褚亮",
        "realName": "褚亮",
        "school": "苏州高新区实验初级中学",
        "phone": "13800138000",
    }


def test_list_students_includes_profile_school_and_phone(monkeypatch):
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
    )
    monkeypatch.setattr(
        server,
        "_load_students",
        lambda client, group_id: [
            Student(uid="u1", username="SZS001", nickname="学生1")
        ],
    )
    monkeypatch.setattr(
        server,
        "_load_student_profile",
        lambda client, uid, username: {
            "school": "苏州高新区实验初级中学",
            "phone": "13800138000",
        },
    )

    result = server.list_students(session, 2186)

    assert result == [
        {
            "uid": "u1",
            "username": "SZS001",
            "nickname": "学生1",
            "realName": "学生1",
            "school": "苏州高新区实验初级中学",
            "phone": "13800138000",
        }
    ]


def test_list_problem_choices_marks_previous_training_problems(monkeypatch):
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
        problems_by_training={
            (11, ""): [{"problemId": "P1001", "title": "课堂题"}],
            (10, ""): [{"problemId": "P0901", "title": "课后题"}],
        },
    )
    monkeypatch.setattr(
        server,
        "_load_trainings",
        lambda client, group_id: [
            Training(training_id=10, title="前一列表"),
            Training(training_id=11, title="当前列表"),
        ],
    )

    choices = server.list_problem_choices(
        session,
        group_id=2186,
        training_id=11,
        training_password="",
        include_previous=True,
    )

    assert choices == [
        {"problemId": "P1001", "title": "课堂题", "source": "current"},
        {
            "problemId": "P0901",
            "title": "课后题",
            "source": "previous",
            "trainingId": 10,
            "trainingTitle": "前一列表",
        },
    ]


def test_generate_report_uses_previous_list_for_after_class_problems(
    tmp_path, monkeypatch
):
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    progress_call: dict[str, object] = {}
    rendered: dict[str, object] = {}
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
    )

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(
        server,
        "get_config",
        lambda: AppConfig(
            account=None,
            password=None,
            template_path=template_path,
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr(
        server,
        "_find_team",
        lambda fake_session, group_id: type("Team", (), {"name": "测试班"})(),
    )
    monkeypatch.setattr(
        server,
        "_find_training",
        lambda fake_session, group_id, training_id: Training(
            training_id=11,
            title="当前列表",
        ),
    )
    monkeypatch.setattr(
        server,
        "list_trainings",
        lambda fake_session, group_id: [
            {"trainingId": 10, "title": "前一列表"},
            {"trainingId": 11, "title": "当前列表"},
        ],
    )

    def fake_list_problems(fake_session, training_id, training_password):
        if training_id == 11:
            return [
                {"problemId": "P1001", "title": "课堂题"},
                {"problemId": "P1002", "title": "当前课后题"},
            ]
        if training_id == 10:
            return [{"problemId": "P0901", "title": "上一课后题"}]
        raise AssertionError(training_id)

    def fake_load_rank_records(client, training_id):
        if training_id == 11:
            return [{"uid": "u1", "submissionInfo": {"P1001": {"isAC": True}}}]
        if training_id == 10:
            return [{"uid": "u1", "submissionInfo": {"P0901": {"isAC": True}}}]
        raise AssertionError(training_id)

    def fake_build_progress_rows(
        students,
        problems,
        rank_records,
        after_class_problems=None,
        after_class_rank_records=None,
        absent_student_uids=None,
    ):
        progress_call["students"] = students
        progress_call["problems"] = problems
        progress_call["rank_records"] = rank_records
        progress_call["after_class_problems"] = after_class_problems
        progress_call["after_class_rank_records"] = after_class_rank_records
        return ["row"]

    def fake_render_report(request, problems, after_class_problems, rows, output_path):
        rendered["after_class_problems"] = after_class_problems
        rendered["rows"] = rows
        Workbook().save(output_path)

    monkeypatch.setattr(server, "list_problems", fake_list_problems)
    monkeypatch.setattr(server, "_load_students", lambda client, group_id: [
        Student(uid="u1", username="s1", nickname="学生1")
    ])
    monkeypatch.setattr(server, "_load_rank_records", fake_load_rank_records)
    monkeypatch.setattr(server, "build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr(server, "render_report", fake_render_report)

    result = server.generate_report(
        session,
        {
            "teamId": 2186,
            "trainingId": 11,
            "problems": ["课堂题"],
            "afterClassProblems": ["当前课后题", "上一课后题"],
        },
    )

    assert result["filename"].endswith("学情反馈表.xlsx")
    assert [problem.title for problem in rendered["after_class_problems"]] == [
        "上一课后题"
    ]
    assert [problem.title for problem in progress_call["after_class_problems"]] == [
        "上一课后题"
    ]
    assert progress_call["after_class_rank_records"] == [
        {"uid": "u1", "submissionInfo": {"P0901": {"isAC": True}}}
    ]


def test_generate_report_accepts_after_class_problem_ids_from_toolbox_payload(
    tmp_path, monkeypatch
):
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    progress_call: dict[str, object] = {}
    rendered: dict[str, object] = {}
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
    )

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(
        server,
        "get_config",
        lambda: AppConfig(
            account=None,
            password=None,
            template_path=template_path,
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr(
        server,
        "_find_team",
        lambda fake_session, group_id: type("Team", (), {"name": "测试班"})(),
    )
    monkeypatch.setattr(
        server,
        "_find_training",
        lambda fake_session, group_id, training_id: Training(
            training_id=11,
            title="当前列表",
        ),
    )
    monkeypatch.setattr(
        server,
        "list_trainings",
        lambda fake_session, group_id: [
            {"trainingId": 10, "title": "前一列表"},
            {"trainingId": 11, "title": "当前列表"},
        ],
    )

    def fake_list_problems(fake_session, training_id, training_password):
        if training_id == 11:
            return [{"problemId": "P1001", "title": "课堂题"}]
        if training_id == 10:
            return [{"problemId": "P0901", "title": "上一课后题"}]
        raise AssertionError(training_id)

    def fake_load_rank_records(client, training_id):
        if training_id == 11:
            return [{"uid": "u1", "submissionInfo": {"P1001": {"isAC": True}}}]
        if training_id == 10:
            return [{"uid": "u1", "submissionInfo": {"P0901": {"isAC": True}}}]
        raise AssertionError(training_id)

    def fake_build_progress_rows(
        students,
        problems,
        rank_records,
        after_class_problems=None,
        after_class_rank_records=None,
        absent_student_uids=None,
    ):
        progress_call["after_class_problems"] = after_class_problems
        progress_call["after_class_rank_records"] = after_class_rank_records
        return ["row"]

    def fake_render_report(request, problems, after_class_problems, rows, output_path):
        rendered["after_class_problems"] = after_class_problems
        rendered["rows"] = rows
        Workbook().save(output_path)

    monkeypatch.setattr(server, "list_problems", fake_list_problems)
    monkeypatch.setattr(server, "_load_students", lambda client, group_id: [
        Student(uid="u1", username="s1", nickname="学生1")
    ])
    monkeypatch.setattr(server, "_load_rank_records", fake_load_rank_records)
    monkeypatch.setattr(server, "build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr(server, "render_report", fake_render_report)

    result = server.generate_report(
        session,
        {
            "teamId": 2186,
            "trainingId": 11,
            "problems": ["P1001"],
            "afterClassProblems": ["P0901"],
        },
    )

    assert result["filename"].endswith("学情反馈表.xlsx")
    assert [problem.problem_id for problem in rendered["after_class_problems"]] == [
        "P0901"
    ]
    assert [problem.problem_id for problem in progress_call["after_class_problems"]] == [
        "P0901"
    ]
    assert progress_call["after_class_rank_records"] == [
        {"uid": "u1", "submissionInfo": {"P0901": {"isAC": True}}}
    ]


def test_generate_report_passes_absent_student_uids_to_progress_rows(
    tmp_path, monkeypatch
):
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    progress_call: dict[str, object] = {}
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
    )

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(
        server,
        "get_config",
        lambda: AppConfig(
            account=None,
            password=None,
            template_path=template_path,
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr(
        server,
        "_find_team",
        lambda fake_session, group_id: type("Team", (), {"name": "测试班"})(),
    )
    monkeypatch.setattr(
        server,
        "_find_training",
        lambda fake_session, group_id, training_id: Training(
            training_id=11,
            title="当前列表",
        ),
    )
    monkeypatch.setattr(
        server,
        "list_trainings",
        lambda fake_session, group_id: [{"trainingId": 11, "title": "当前列表"}],
    )
    monkeypatch.setattr(
        server,
        "list_problems",
        lambda fake_session, training_id, training_password: [
            {"problemId": "P1001", "title": "课堂题"}
        ],
    )
    monkeypatch.setattr(server, "_load_students", lambda client, group_id: [
        Student(uid="u1", username="s1", nickname="学生1")
    ])
    monkeypatch.setattr(server, "_load_rank_records", lambda client, training_id: [])

    def fake_build_progress_rows(
        students,
        problems,
        rank_records,
        after_class_problems=None,
        after_class_rank_records=None,
        absent_student_uids=None,
    ):
        progress_call["absent_student_uids"] = absent_student_uids
        return []

    monkeypatch.setattr(server, "build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr(server, "render_report", lambda *args, **kwargs: Workbook().save(kwargs["output_path"]))

    result = server.generate_report(
        session,
        {
            "teamId": 2186,
            "trainingId": 11,
            "problems": ["P1001"],
            "absentStudentUids": ["u1"],
        },
    )

    assert result["filename"].endswith("学情反馈表.xlsx")
    assert progress_call["absent_student_uids"] == {"u1"}


def test_generate_report_accepts_problem_ids_from_toolbox_payload(
    tmp_path, monkeypatch
):
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    progress_call: dict[str, object] = {}
    rendered: dict[str, object] = {}
    session = server.UserSession(
        session_id="session-id",
        user_id=1,
        account="13800138000",
        client=object(),
    )

    monkeypatch.setattr(server, "ROOT", tmp_path)
    monkeypatch.setattr(
        server,
        "get_config",
        lambda: AppConfig(
            account=None,
            password=None,
            template_path=template_path,
            output_dir=tmp_path,
        ),
    )
    monkeypatch.setattr(
        server,
        "_find_team",
        lambda fake_session, group_id: type("Team", (), {"name": "测试班"})(),
    )
    monkeypatch.setattr(
        server,
        "_find_training",
        lambda fake_session, group_id, training_id: Training(
            training_id=11,
            title="当前列表",
        ),
    )
    monkeypatch.setattr(
        server,
        "list_trainings",
        lambda fake_session, group_id: [
            {"trainingId": 11, "title": "当前列表"},
        ],
    )

    def fake_list_problems(fake_session, training_id, training_password):
        assert training_id == 11
        return [
            {"problemId": "P3480", "title": "电梯问题"},
            {"problemId": "P3481", "title": "分数计数"},
        ]

    def fake_build_progress_rows(
        students,
        problems,
        rank_records,
        after_class_problems=None,
        after_class_rank_records=None,
        absent_student_uids=None,
    ):
        progress_call["problems"] = problems
        return ["row"]

    def fake_render_report(request, problems, after_class_problems, rows, output_path):
        rendered["problems"] = problems
        rendered["rows"] = rows
        Workbook().save(output_path)

    monkeypatch.setattr(server, "list_problems", fake_list_problems)
    monkeypatch.setattr(server, "_load_students", lambda client, group_id: [
        Student(uid="u1", username="s1", nickname="学生1")
    ])
    monkeypatch.setattr(server, "_load_rank_records", lambda client, training_id: [])
    monkeypatch.setattr(server, "build_progress_rows", fake_build_progress_rows)
    monkeypatch.setattr(server, "render_report", fake_render_report)

    result = server.generate_report(
        session,
        {
            "teamId": 2186,
            "trainingId": 11,
            "problems": ["P3480", "P3481"],
        },
    )

    assert result["filename"].endswith("学情反馈表.xlsx")
    assert [problem.problem_id for problem in rendered["problems"]] == [
        "P3480",
        "P3481",
    ]
    assert [problem.problem_id for problem in progress_call["problems"]] == [
        "P3480",
        "P3481",
    ]
