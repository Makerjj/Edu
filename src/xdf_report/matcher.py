from dataclasses import dataclass
from typing import Sequence, TypeVar

from .models import Problem, Team, Training

T = TypeVar("T")


class MatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProblemQueryMatchResult:
    query: str
    problem: Problem | None
    error: str | None


def _contains(haystack: str, needle: str) -> bool:
    return needle.lower() in haystack.lower()


def _normalize_problem_id(value: str) -> str:
    return value.strip().upper()


def _normalize_title(value: str) -> str:
    return value.strip().lower()


def match_single_by_name(
    items: Sequence[T], query: str, attr: str, label: str
) -> T:
    normalized_query = query.strip()
    if not normalized_query:
        raise MatchError(f"{label}查询不能为空")
    matches = [
        item for item in items if _contains(getattr(item, attr), normalized_query)
    ]
    if not matches:
        samples = ", ".join(getattr(item, attr) for item in items[:10])
        raise MatchError(f"未找到{label}: {normalized_query}。候选: {samples}")
    if len(matches) > 1:
        names = ", ".join(getattr(item, attr) for item in matches)
        raise MatchError(f"{label}匹配到多个结果: {names}")
    return matches[0]


def match_team_by_name(teams: Sequence[Team], query: str) -> Team:
    return match_single_by_name(teams, query, "name", "团队")


def match_training_by_name(trainings: Sequence[Training], query: str) -> Training:
    return match_single_by_name(trainings, query, "title", "训练")


def _match_problem_query(problems: Sequence[Problem], query: str) -> Problem:
    normalized_query = _normalize_problem_id(query)
    title_query = query.strip()
    if not title_query:
        raise MatchError("题目查询不能为空")
    exact = [
        problem
        for problem in problems
        if _normalize_problem_id(problem.problem_id) == normalized_query
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        names = ", ".join(f"{problem.problem_id}({problem.title})" for problem in exact)
        raise MatchError(f"题目匹配到多个结果: {query} -> {names}")
    exact_title = [
        problem
        for problem in problems
        if _normalize_title(problem.title) == _normalize_title(title_query)
    ]
    if len(exact_title) == 1:
        return exact_title[0]
    if len(exact_title) > 1:
        names = ", ".join(
            f"{problem.problem_id}({problem.title})" for problem in exact_title
        )
        raise MatchError(f"题目匹配到多个结果: {query} -> {names}")
    by_title = [problem for problem in problems if _contains(problem.title, title_query)]
    if not by_title:
        raise MatchError(f"未找到题目: {query}")
    if len(by_title) > 1:
        names = ", ".join(f"{problem.problem_id}({problem.title})" for problem in by_title)
        raise MatchError(f"题目匹配到多个结果: {query} -> {names}")
    return by_title[0]


def try_match_problem_query(
    problems: Sequence[Problem], query: str
) -> Problem | str:
    try:
        result = ProblemQueryMatchResult(
            query=query,
            problem=_match_problem_query(problems, query),
            error=None,
        )
        return result.problem
    except MatchError as error:
        result = ProblemQueryMatchResult(query=query, problem=None, error=str(error))
        return result.error


def match_problem_queries(
    problems: Sequence[Problem], queries: Sequence[str]
) -> list[Problem]:
    matched: list[Problem] = []
    for query in queries:
        matched.append(_match_problem_query(problems, query))
    return matched
