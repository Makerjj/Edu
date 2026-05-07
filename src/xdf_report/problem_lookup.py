from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .api import OJClient
from .auth import DingdangAuthClient
from .cli import _extract_student_code
from .config import load_config


@dataclass(frozen=True)
class ProblemSearchResult:
    pid: int
    problem_id: str
    title: str
    difficulty: int | None
    tags: list[str]
    total: int | None
    ac: int | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按题号或题名搜索 code.xdf.cn OJ 题目")
    parser.add_argument("query", help="题号或题名关键词，例如 GESP251203T2 或 小杨")
    parser.add_argument(
        "--config",
        default="config.json",
        help="账号配置 JSON 路径，默认 ./config.json",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="搜索结果数量，默认 10",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="输出格式，默认 markdown",
    )
    parser.add_argument(
        "--no-detail",
        action="store_true",
        help="只输出搜索结果，不拉取题面详情",
    )
    return parser


def login_oj_from_config(config_path: Path) -> OJClient:
    config = load_config(config_path if config_path.exists() else None)
    auth_client = DingdangAuthClient()
    dingdang_token = auth_client.login(config.account or "", config.password or "")
    student_code = _extract_student_code(auth_client.get_students(dingdang_token))
    auth_session = auth_client.login_oj(dingdang_token, student_code)
    return OJClient(auth_session.oj_token)


def search_problems(
    client: OJClient, query: str, limit: int = 10
) -> list[ProblemSearchResult]:
    payload = client.get(
        "/get-problem-list",
        {"currentPage": 1, "limit": limit, "keyword": query},
    )
    records = payload.get("data", {}).get("records", [])
    results: list[ProblemSearchResult] = []
    for record in records:
        problem_id = record.get("problemId")
        title = record.get("title")
        pid = record.get("pid")
        if not problem_id or not title or pid is None:
            continue
        tags = [
            str(tag["name"])
            for tag in record.get("tags", [])
            if isinstance(tag, dict) and tag.get("name")
        ]
        results.append(
            ProblemSearchResult(
                pid=int(pid),
                problem_id=str(problem_id),
                title=str(title),
                difficulty=record.get("difficulty"),
                tags=tags,
                total=record.get("total"),
                ac=record.get("ac"),
            )
        )
    return results


def get_problem_detail(client: OJClient, problem_id: str) -> dict[str, Any]:
    payload = client.get("/get-problem-detail", {"problemId": problem_id})
    return payload.get("data", {}).get("problem", {})


def choose_best_result(
    results: list[ProblemSearchResult], query: str
) -> ProblemSearchResult | None:
    if not results:
        return None
    normalized_query = query.strip().upper()
    for result in results:
        if result.problem_id.upper() == normalized_query:
            return result
    return results[0]


def _strip_markup(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"</input>\s*<output>", "\n\n输出：\n", text)
    text = re.sub(r"<input>", "输入：\n", text)
    text = re.sub(r"</?output>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _code_block(label: str, value: str) -> str:
    text = _strip_markup(value)
    if not text:
        return ""
    return f"{label}\n\n```text\n{text}\n```"


def render_markdown(
    result: ProblemSearchResult, detail: dict[str, Any] | None = None
) -> str:
    lines = [
        f"# {result.problem_id} {result.title}",
        "",
        f"- PID: `{result.pid}`",
        f"- 标签: {', '.join(result.tags) if result.tags else '无'}",
    ]
    if result.total is not None and result.ac is not None:
        lines.append(f"- 提交/通过: {result.total}/{result.ac}")
    if not detail:
        return "\n".join(lines).strip()

    description = _strip_markup(str(detail.get("description") or ""))
    problem_input = _strip_markup(str(detail.get("input") or ""))
    problem_output = _strip_markup(str(detail.get("output") or ""))
    examples = str(detail.get("examples") or "")
    hint = _strip_markup(str(detail.get("hint") or ""))

    if description:
        lines += ["", "## 题意", "", description]
    if problem_input:
        lines += ["", "## 输入", "", problem_input]
    if problem_output:
        lines += ["", "## 输出", "", problem_output]
    if examples:
        rendered_examples = _code_block("## 样例", examples)
        if rendered_examples:
            lines += ["", rendered_examples]
    if hint:
        lines += ["", "## 提示", "", hint]
    return "\n".join(lines).strip()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = login_oj_from_config(Path(args.config))
    results = search_problems(client, args.query, args.limit)
    selected = choose_best_result(results, args.query)
    if selected is None:
        raise SystemExit(f"未找到题目: {args.query}")

    detail = None if args.no_detail else get_problem_detail(client, selected.problem_id)
    if args.format == "json":
        payload = {
            "selected": selected.__dict__,
            "results": [result.__dict__ for result in results],
            "detail": detail,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(selected, detail))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
