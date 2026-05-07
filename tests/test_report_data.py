from src.xdf_report.models import Problem, Student
from src.xdf_report.report_data import build_progress_rows


def test_build_progress_rows_marks_ac_as_check():
    students = [Student(uid="u1", username="s1", nickname="学生1")]
    problems = [Problem(problem_id="P1001", title="找苹果")]
    rank_records = [{"uid": "u1", "submissionInfo": {"P1001": {"isAC": True}}}]

    rows = build_progress_rows(students, problems, rank_records)

    assert rows[0].completion_by_problem["P1001"] == "✅"


def test_build_progress_rows_leaves_blank_for_non_ac():
    students = [Student(uid="u2", username="s2", nickname="学生2")]
    problems = [Problem(problem_id="P1002", title="字典找字")]
    rank_records = [{"uid": "u2", "submissionInfo": {"P1002": {"isAC": False}}}]

    rows = build_progress_rows(students, problems, rank_records)

    assert rows[0].completion_by_problem["P1002"] == ""


def test_build_progress_rows_handles_missing_rank_record():
    students = [Student(uid="u3", username="s3", nickname="学生3")]
    problems = [Problem(problem_id="P1003", title="查找")]
    rows = build_progress_rows(students, problems, [])

    assert rows[0].completion_by_problem["P1003"] == ""


def test_build_progress_rows_includes_all_requested_problems():
    students = [Student(uid="u4", username="s4", nickname="学生4")]
    problems = [
        Problem(problem_id="P1004", title="字典找字"),
        Problem(problem_id="P1005", title="排序"),
    ]
    rank_records = [
        {"uid": "u4", "submissionInfo": {"P1004": {"isAC": True}}},
    ]

    rows = build_progress_rows(students, problems, rank_records)

    completion = rows[0].completion_by_problem
    assert completion["P1004"] == "✅"
    assert completion["P1005"] == ""


def test_build_progress_rows_tracks_in_class_and_after_class_sections():
    students = [Student(uid="u5", username="s5", nickname="学生5")]
    problems = [Problem(problem_id="P1006", title="课堂题")]
    after_class_problems = [Problem(problem_id="P2001", title="课后题")]
    rank_records = [{"uid": "u5", "submissionInfo": {"P1006": {"isAC": True}}}]
    after_class_rank_records = [{"uid": "u5", "submissionInfo": {"P2001": {"isAC": True}}}]

    rows = build_progress_rows(
        students,
        problems,
        rank_records,
        after_class_problems=after_class_problems,
        after_class_rank_records=after_class_rank_records,
    )

    assert rows[0].completion_by_problem["P1006"] == "✅"
    assert rows[0].after_class_completion_by_problem["P2001"] == "✅"


def test_build_progress_rows_matches_numeric_rank_record_uid_to_string_student_uid():
    students = [Student(uid="0", username="s6", nickname="学生6")]
    problems = [Problem(problem_id="P3001", title="数字学号题")]
    rank_records = [{"uid": 0, "submissionInfo": {"P3001": {"isAC": True}}}]

    rows = build_progress_rows(students, problems, rank_records)

    assert rows[0].completion_by_problem["P3001"] == "✅"
