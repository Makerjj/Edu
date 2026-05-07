import pytest

from src.xdf_report.matcher import (
    MatchError,
    match_problem_queries,
    match_team_by_name,
    try_match_problem_query,
)
from src.xdf_report.models import Problem, Team


def test_match_problem_queries_prefers_problem_id():
    problems = [
        Problem(problem_id="P1001", title="找苹果"),
        Problem(problem_id="P1002", title="字典找字"),
    ]

    matched = match_problem_queries(problems, ["P1002", "找苹果"])

    assert [item.problem_id for item in matched] == ["P1002", "P1001"]


def test_match_problem_queries_normalizes_problem_id_query_before_title_matching():
    problems = [
        Problem(problem_id="P1001", title="找苹果"),
        Problem(problem_id="P1002", title="字典找字"),
    ]

    matched = match_problem_queries(problems, ["  p1002  "])

    assert [item.problem_id for item in matched] == ["P1002"]


def test_match_problem_queries_raises_on_ambiguous_exact_problem_id():
    problems = [
        Problem(problem_id="P1002", title="字典找字A"),
        Problem(problem_id="P1002", title="字典找字B"),
    ]

    with pytest.raises(MatchError) as error:
        match_problem_queries(problems, ["P1002"])

    assert "题目匹配到多个结果" in str(error.value)
    assert "P1002" in str(error.value)


def test_match_problem_queries_prefers_exact_title_before_contains_matching():
    problems = [
        Problem(problem_id="P1001", title="二分查找"),
        Problem(problem_id="P1002", title="查找"),
        Problem(problem_id="P1003", title="查找最接近的元素"),
    ]

    matched = match_problem_queries(problems, ["查找"])

    assert [item.problem_id for item in matched] == ["P1002"]


def test_match_problem_queries_raises_clear_error_for_blank_query():
    problems = [
        Problem(problem_id="P1001", title="找苹果"),
        Problem(problem_id="P1002", title="字典找字"),
    ]

    with pytest.raises(MatchError) as error:
        match_problem_queries(problems, ["   "])

    assert str(error.value) == "题目查询不能为空"


def test_try_match_problem_query_returns_reason_instead_of_raising():
    problems = [
        Problem(problem_id="P1001", title="找苹果"),
        Problem(problem_id="P1002", title="字典找字"),
    ]

    result = try_match_problem_query(problems, "不存在的题目")

    assert result == "未找到题目: 不存在的题目"


def test_try_match_problem_query_returns_clear_error_for_blank_query():
    problems = [
        Problem(problem_id="P1001", title="找苹果"),
        Problem(problem_id="P1002", title="字典找字"),
    ]

    result = try_match_problem_query(problems, "   ")

    assert result == "题目查询不能为空"


def test_try_match_problem_query_returns_problem_on_success():
    problems = [
        Problem(problem_id="P1001", title="找苹果"),
        Problem(problem_id="P1002", title="字典找字"),
    ]

    result = try_match_problem_query(problems, "P1002")

    assert result == problems[1]


def test_match_team_by_name_raises_clear_error_for_blank_query():
    teams = [
        Team(group_id=1, name="周六一档易生活102"),
        Team(group_id=2, name="周日二档春季班201"),
    ]

    with pytest.raises(MatchError) as error:
        match_team_by_name(teams, "   ")

    assert str(error.value) == "团队查询不能为空"


def test_match_team_by_name_strips_whitespace_for_matching():
    teams = [
        Team(group_id=1, name="周六一档易生活102"),
        Team(group_id=2, name="周日二档春季班201"),
    ]

    matched = match_team_by_name(teams, "  易生活102  ")

    assert matched == teams[0]


def test_match_team_by_name_raises_for_no_match_with_candidates():
    teams = [
        Team(group_id=1, name="周六一档易生活102"),
        Team(group_id=2, name="周日二档春季班201"),
    ]

    with pytest.raises(MatchError) as error:
        match_team_by_name(teams, "不存在的班级")

    message = str(error.value)
    assert "未找到团队" in message
    assert "候选" in message
