from pathlib import Path

from src.xdf_report.config import AppConfig
from src.xdf_report.list_team_students import build_parser, main


def test_build_parser_reads_team_and_optional_config() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--team",
            "C1-3",
            "--config",
            "custom.json",
        ]
    )

    assert args.team == "C1-3"
    assert args.config == "custom.json"


def test_main_prints_team_students_with_fake_clients(monkeypatch, capsys) -> None:
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

    monkeypatch.setattr(
        "src.xdf_report.list_team_students.load_config",
        lambda path: AppConfig(
            account="19951913492",
            password="qwe123456",
            template_path=Path("tests/fixtures/template.xlsx"),
            output_dir=Path("out"),
        ),
    )
    monkeypatch.setattr(
        "src.xdf_report.list_team_students.ensure_credentials",
        lambda config: config,
    )
    monkeypatch.setattr("src.xdf_report.list_team_students.DingdangAuthClient", FakeAuthClient)
    monkeypatch.setattr("src.xdf_report.list_team_students.OJClient", FakeOJClient)
    monkeypatch.setattr(
        "src.xdf_report.list_team_students.resolve_team",
        lambda client, query: type("Team", (), {"name": "周六一档易生活102-C1-3", "group_id": 2186})(),
    )
    monkeypatch.setattr(
        "src.xdf_report.list_team_students._load_students",
        lambda client, group_id: [
            type("Student", (), {"uid": "10001", "username": "jason_a", "nickname": "Jason"})(),
            type("Student", (), {"uid": "10002", "username": "jason_b", "nickname": "Jason"})(),
        ],
    )

    exit_code = main(["--team", "C1-3"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip().splitlines() == [
        "团队: 周六一档易生活102-C1-3 (gid=2186)",
        "uid\tusername\tnickname",
        "10001\tjason_a\tJason",
        "10002\tjason_b\tJason",
    ]
