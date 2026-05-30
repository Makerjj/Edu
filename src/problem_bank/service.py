from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.xdf_report.api import OJClient
from src.xdf_report.problem_lookup import get_problem_detail, render_markdown, search_problems


@dataclass(frozen=True)
class ProblemBankSearch:
    query: str
    limit: int = 8
    include_detail: bool = True


def search_problem_bank(client: OJClient, request: ProblemBankSearch) -> dict[str, Any]:
    query = request.query.strip()
    if not query:
        raise ValueError("请输入题号或题名关键词")

    limit = max(1, min(int(request.limit or 8), 20))
    results = search_problems(client, query, limit=limit)
    items: list[dict[str, Any]] = []
    for result in results:
        detail = get_problem_detail(client, result.problem_id) if request.include_detail else None
        items.append(
            {
                "pid": result.pid,
                "problemId": result.problem_id,
                "title": result.title,
                "difficulty": result.difficulty,
                "tags": result.tags,
                "total": result.total,
                "ac": result.ac,
                "markdown": render_markdown(result, detail),
            }
        )
    return {
        "query": query,
        "limit": limit,
        "count": len(items),
        "items": items,
    }
