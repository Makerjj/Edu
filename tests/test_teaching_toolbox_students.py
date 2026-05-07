import json

from teaching_toolbox import server


def test_save_students_writes_selected_students_with_edited_real_name(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        server,
        "_find_team",
        lambda group_id: type("Team", (), {"group_id": group_id, "name": "测试班"})(),
    )

    result = server.save_students(
        {
            "teamId": 2186,
            "filename": "students.test.json",
            "students": [
                {
                    "uid": "u1",
                    "username": "SZS001",
                    "nickname": "Jason 褚亮",
                    "realName": "褚亮",
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
    }
