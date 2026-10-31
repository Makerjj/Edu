from pathlib import Path

from openpyxl import Workbook, load_workbook

from src.xdf_report.excel_template import render_report
from src.xdf_report.models import Problem, ReportRequest, Student, StudentProgress


def _fill_key(cell) -> tuple[str, str, str]:
    return (
        cell.fill.fill_type,
        cell.fill.fgColor.type,
        cell.fill.fgColor.rgb or cell.fill.fgColor.indexed or cell.fill.fgColor.theme,
    )


def _border_styles(cell) -> tuple[str | None, str | None, str | None, str | None]:
    return (
        cell.border.left.style,
        cell.border.right.style,
        cell.border.top.style,
        cell.border.bottom.style,
    )


def _has_visible_box_border(cell) -> bool:
    return all(style is not None for style in _border_styles(cell))


def _make_request(
    tmp_path: Path,
    problem_queries: list[str],
    after_class_problem_queries: list[str] | None = None,
    homework_only: bool = False,
) -> ReportRequest:
    return ReportRequest(
        team_name="易生活102 C1",
        training_name="二分查找",
        problem_queries=problem_queries,
        template_path=Path("tests/fixtures/template.xlsx"),
        output_dir=tmp_path,
        after_class_problem_queries=after_class_problem_queries or [],
        homework_only=homework_only,
    )


def test_render_report_homework_only_hides_classroom_columns(tmp_path: Path) -> None:
    output_path = tmp_path / "homework.xlsx"
    problems = [
        Problem(problem_id="P1001", title="骨牌问题"),
        Problem(problem_id="P1002", title="纸张对折"),
    ]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            completion_by_problem={"P1001": "✅", "P1002": ""},
        )
    ]

    render_report(
        request=_make_request(
            tmp_path,
            ["骨牌问题", "纸张对折"],
            homework_only=True,
        ),
        problems=problems,
        after_class_problems=[],
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]
    assert sheet.max_column == 3
    assert sheet["A1"].value == "姓名"
    assert sheet["B1"].value == "本次作业完成情况"
    assert sheet["B2"].value == "骨牌问题"
    assert sheet["C2"].value == "纸张对折"
    assert sheet["A3"].value == "学生1"
    assert sheet["B3"].value == "✅"
    assert sheet["C3"].value is None


def test_render_report_writes_expected_cells_from_template(tmp_path: Path) -> None:
    output_path = tmp_path / "result.xlsx"
    request = _make_request(tmp_path, ["找苹果", "摘梨"])
    problems = [
        Problem(problem_id="P1001", title="找苹果"),
        Problem(problem_id="P1002", title="摘梨"),
    ]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            completion_by_problem={"P1001": "✅", "P1002": ""},
        ),
        StudentProgress(
            student=Student(uid="u2", username="s2", nickname="学生2"),
            completion_by_problem={"P1001": "", "P1002": "✅"},
        ),
    ]
    after_class_problems = [
        Problem(problem_id="P2001", title="验证密码"),
        Problem(problem_id="P2002", title="逢7过"),
    ]

    render_report(
        request=_make_request(
            tmp_path,
            ["找苹果", "摘梨"],
            ["验证密码", "逢7过"],
        ),
        problems=problems,
        after_class_problems=after_class_problems,
        rows=rows,
        output_path=output_path,
    )

    workbook = load_workbook(output_path)

    assert workbook.sheetnames == ["结果"]

    sheet = workbook["结果"]
    assert sheet["A3"].value == "学生1"
    assert sheet["A4"].value == "学生2"
    assert sheet["A5"].value is None
    assert sheet["F2"].value == "找苹果"
    assert sheet["G2"].value == "摘梨"
    assert sheet["H2"].value is None
    assert sheet["J1"].value == "上周课后练习完成情况"
    assert sheet["J2"].value == "验证密码"
    assert sheet["K2"].value == "逢7过"
    assert sheet["L2"].value is None
    assert "备注" not in [sheet.cell(1, col).value for col in range(1, sheet.max_column + 1)]
    assert "出门测成绩" not in [
        sheet.cell(1, col).value for col in range(1, sheet.max_column + 1)
    ]
    assert sheet["F3"].value == "✅"
    assert sheet["G3"].value is None
    assert sheet["F4"].value is None
    assert sheet["G4"].value == "✅"
    assert sheet["J3"].value is None
    assert sheet["K3"].value is None
    assert sheet["J4"].value is None
    assert sheet["K4"].value is None


def test_render_report_sets_student_rows_to_readable_height(tmp_path: Path) -> None:
    output_path = tmp_path / "result.xlsx"
    problems = [Problem(problem_id="P1001", title="找苹果")]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            completion_by_problem={"P1001": "✅"},
        ),
        StudentProgress(
            student=Student(uid="u2", username="s2", nickname="学生2"),
            completion_by_problem={"P1001": ""},
        ),
    ]

    render_report(
        request=_make_request(tmp_path, ["找苹果"]),
        problems=problems,
        after_class_problems=[],
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]

    assert sheet.row_dimensions[3].height == 28
    assert sheet.row_dimensions[4].height == 28


def test_render_report_extends_students_beyond_top_sample_block(tmp_path: Path) -> None:
    output_path = tmp_path / "result.xlsx"
    problems = [Problem(problem_id="P1001", title="找苹果")]
    rows = [
        StudentProgress(
            student=Student(uid=f"u{index}", username=f"s{index}", nickname=f"学生{index}"),
            completion_by_problem={"P1001": "✅" if index % 2 else ""},
        )
        for index in range(1, 7)
    ]

    render_report(
        request=_make_request(tmp_path, ["找苹果"]),
        problems=problems,
        after_class_problems=[],
        rows=rows,
        output_path=output_path,
    )

    workbook = load_workbook(output_path)

    assert workbook.sheetnames == ["结果"]

    sheet = workbook["结果"]
    assert sheet.max_row == 8
    assert [sheet.cell(row, 1).value for row in range(3, 9)] == [
        "学生1",
        "学生2",
        "学生3",
        "学生4",
        "学生5",
        "学生6",
    ]
    assert sheet["A9"].value is None
    assert sheet["A13"].value is None


def test_render_report_writes_after_class_data_in_after_class_region(tmp_path: Path) -> None:
    output_path = tmp_path / "result.xlsx"
    problems = [Problem(problem_id="P1001", title="找苹果")]
    after_class_problems = [
        Problem(problem_id="P2001", title="验证密码"),
        Problem(problem_id="P2002", title="逢7过"),
    ]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            completion_by_problem={"P1001": "✅"},
            after_class_completion_by_problem={"P2001": "✅", "P2002": ""},
        ),
        StudentProgress(
            student=Student(uid="u2", username="s2", nickname="学生2"),
            completion_by_problem={"P1001": ""},
            after_class_completion_by_problem={"P2001": "", "P2002": "✅"},
        ),
    ]

    render_report(
        request=_make_request(
            tmp_path,
            ["找苹果"],
            ["验证密码", "逢7过"],
        ),
        problems=problems,
        after_class_problems=after_class_problems,
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]

    assert sheet["F2"].value == "找苹果"
    assert sheet["F3"].value == "✅"
    assert sheet["F4"].value is None
    assert sheet["J2"].value == "验证密码"
    assert sheet["K2"].value == "逢7过"
    assert sheet["J3"].value == "✅"
    assert sheet["K3"].value is None
    assert sheet["J4"].value is None
    assert sheet["K4"].value == "✅"


def test_render_report_places_after_class_after_six_in_class_problems(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "result.xlsx"
    problems = [
        Problem(problem_id=f"P10{index}", title=f"课堂题{index}")
        for index in range(1, 7)
    ]
    after_class_problems = [
        Problem(problem_id="P2001", title="课后题1"),
        Problem(problem_id="P2002", title="课后题2"),
    ]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            completion_by_problem={
                problem.problem_id: "✅" for problem in problems
            },
            after_class_completion_by_problem={"P2001": "✅", "P2002": ""},
        )
    ]

    render_report(
        request=_make_request(
            tmp_path,
            [problem.title for problem in problems],
            ["课后题1", "课后题2"],
        ),
        problems=problems,
        after_class_problems=after_class_problems,
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]

    assert [sheet.cell(2, col).value for col in range(6, 12)] == [
        "课堂题1",
        "课堂题2",
        "课堂题3",
        "课堂题4",
        "课堂题5",
        "课堂题6",
    ]
    assert [sheet.cell(3, col).value for col in range(6, 12)] == ["✅"] * 6
    assert sheet["L1"].value == "上周课后练习完成情况"
    assert sheet["L2"].value == "课后题1"
    assert sheet["M2"].value == "课后题2"
    assert sheet["L3"].value == "✅"
    assert sheet["M3"].value is None
    assert _fill_key(sheet["K1"]) == _fill_key(sheet["F1"])
    assert _has_visible_box_border(sheet["K1"])
    assert _fill_key(sheet["L2"]) == _fill_key(sheet["J2"])
    assert _fill_key(sheet["M2"]) == _fill_key(sheet["J2"])
    for coordinate in ("L2", "M2", "L3", "M3"):
        assert _has_visible_box_border(sheet[coordinate])


def test_render_report_extends_after_class_header_style_across_problem_span(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "result.xlsx"
    after_class_problems = [
        Problem(problem_id="P2001", title="A+B还是A-B"),
        Problem(problem_id="P2002", title="拆分两位数"),
        Problem(problem_id="P2003", title="A-B Problem"),
    ]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            after_class_completion_by_problem={"P2001": "✅"},
        )
    ]

    render_report(
        request=_make_request(
            tmp_path,
            [],
            ["A+B还是A-B", "拆分两位数", "A-B Problem"],
        ),
        problems=[],
        after_class_problems=after_class_problems,
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]
    expected_fill = _fill_key(sheet["J1"])

    for coordinate in ("J1", "K1", "L1"):
        assert _fill_key(sheet[coordinate]) == expected_fill
        assert _has_visible_box_border(sheet[coordinate])


def test_render_report_extends_after_class_body_borders_across_problem_span(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "result.xlsx"
    after_class_problems = [
        Problem(problem_id="P2001", title="A+B还是A-B"),
        Problem(problem_id="P2002", title="拆分两位数"),
        Problem(problem_id="P2003", title="A-B Problem"),
    ]
    rows = [
        StudentProgress(
            student=Student(uid=f"u{index}", username=f"s{index}", nickname=f"学生{index}"),
            after_class_completion_by_problem={
                "P2001": "✅" if index % 2 else "",
                "P2002": "",
                "P2003": "✅" if index == 6 else "",
            },
        )
        for index in range(1, 7)
    ]

    render_report(
        request=_make_request(
            tmp_path,
            [],
            ["A+B还是A-B", "拆分两位数", "A-B Problem"],
        ),
        problems=[],
        after_class_problems=after_class_problems,
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]

    for coordinate in ("L3", "L8"):
        assert _has_visible_box_border(sheet[coordinate])


def test_render_report_leaves_after_class_region_blank_when_not_provided(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "result.xlsx"
    problems = [Problem(problem_id="P1001", title="找苹果")]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            completion_by_problem={"P1001": "✅"},
        )
    ]

    render_report(
        request=_make_request(tmp_path, ["找苹果"]),
        problems=problems,
        after_class_problems=[],
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]

    assert sheet["J2"].value is None
    assert sheet["K2"].value is None
    assert sheet["J3"].value is None
    assert sheet["K3"].value is None


def test_render_report_fills_classroom_performance_with_three_stars(tmp_path: Path) -> None:
    output_path = tmp_path / "result.xlsx"
    problems = [Problem(problem_id="P1001", title="找苹果")]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            completion_by_problem={"P1001": "✅"},
        ),
        StudentProgress(
            student=Student(uid="u2", username="s2", nickname="学生2"),
            completion_by_problem={"P1001": ""},
        ),
    ]

    render_report(
        request=_make_request(tmp_path, ["找苹果"]),
        problems=problems,
        after_class_problems=[],
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]

    assert sheet["C3"].value == "🌟🌟🌟"
    assert sheet["D3"].value == "🌟🌟🌟"
    assert sheet["E3"].value == "🌟🌟🌟"
    assert sheet["C4"].value == "🌟🌟🌟"
    assert sheet["D4"].value == "🌟🌟🌟"
    assert sheet["E4"].value == "🌟🌟🌟"


def test_render_report_fills_attendance_with_checkmarks(tmp_path: Path) -> None:
    output_path = tmp_path / "result.xlsx"
    problems = [Problem(problem_id="P1001", title="找苹果")]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            completion_by_problem={"P1001": "✅"},
        ),
        StudentProgress(
            student=Student(uid="u2", username="s2", nickname="学生2"),
            completion_by_problem={"P1001": ""},
        ),
    ]

    render_report(
        request=_make_request(tmp_path, ["找苹果"]),
        problems=problems,
        after_class_problems=[],
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]

    assert sheet["B3"].value == "✅"
    assert sheet["B4"].value == "✅"


def test_render_report_marks_absent_student_without_overwriting_after_class(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "result.xlsx"
    problems = [Problem(problem_id="P1001", title="课堂题")]
    after_class_problems = [Problem(problem_id="P2001", title="课后题")]
    rows = [
        StudentProgress(
            student=Student(uid="u1", username="s1", nickname="学生1"),
            completion_by_problem={"P1001": "请假"},
            after_class_completion_by_problem={"P2001": "✅"},
            is_absent=True,
        )
    ]

    render_report(
        request=_make_request(tmp_path, ["课堂题"], ["课后题"]),
        problems=problems,
        after_class_problems=after_class_problems,
        rows=rows,
        output_path=output_path,
    )

    sheet = load_workbook(output_path)["结果"]

    assert sheet["B3"].value == "请假"
    assert sheet["C3"].value == "请假"
    assert sheet["D3"].value == "请假"
    assert sheet["E3"].value == "请假"
    assert sheet["F3"].value == "请假"
    assert sheet["J3"].value == "✅"


def test_render_report_removes_merged_cells_from_last_student_row(tmp_path: Path) -> None:
    template_path = tmp_path / "merged-tail-template.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "模板"

    for row in range(1, 14):
        for col in range(1, 14):
            sheet.cell(row, col).value = f"r{row}c{col}"

    for row in range(3, 14):
        sheet.cell(row, 1).value = f"模板学生{row}"

    sheet.merge_cells("C13:E13")
    sheet.merge_cells("F13:I13")
    sheet.merge_cells("L13:M13")
    workbook.save(template_path)

    output_path = tmp_path / "result.xlsx"
    rows = [
        StudentProgress(
            student=Student(uid=f"u{index}", username=f"s{index}", nickname=f"学生{index}"),
            completion_by_problem={"P1001": "✅" if index == 11 else ""},
        )
        for index in range(1, 12)
    ]

    request = ReportRequest(
        team_name="易生活102 C1",
        training_name="二分查找",
        problem_queries=["找苹果"],
        template_path=template_path,
        output_dir=tmp_path,
    )

    render_report(
        request=request,
        problems=[Problem(problem_id="P1001", title="找苹果")],
        after_class_problems=[],
        rows=rows,
        output_path=output_path,
    )

    result_sheet = load_workbook(output_path)["结果"]

    merged_ranges = {str(cell_range) for cell_range in result_sheet.merged_cells.ranges}
    assert "C13:E13" not in merged_ranges
    assert "F13:I13" not in merged_ranges
    assert "L13:M13" not in merged_ranges
    assert result_sheet["A13"].value == "学生11"
    assert result_sheet["F13"].value == "✅"
    assert result_sheet["G13"].value is None
