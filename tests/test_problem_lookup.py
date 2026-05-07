from src.xdf_report.problem_lookup import (
    ProblemSearchResult,
    choose_best_result,
    render_markdown,
    search_problems,
)


class FakeClient:
    def get(self, path, params):
        assert path == "/get-problem-list"
        assert params["keyword"] == "小杨"
        return {
            "data": {
                "records": [
                    {
                        "pid": 4699,
                        "problemId": "GESP251203T2",
                        "title": "[GESP 三级]小杨的智慧购物",
                        "difficulty": 0,
                        "tags": [{"name": "数组"}],
                        "total": 249,
                        "ac": 94,
                    }
                ]
            }
        }


def test_search_problems_parses_problem_records():
    results = search_problems(FakeClient(), "小杨")

    assert results == [
        ProblemSearchResult(
            pid=4699,
            problem_id="GESP251203T2",
            title="[GESP 三级]小杨的智慧购物",
            difficulty=0,
            tags=["数组"],
            total=249,
            ac=94,
        )
    ]


def test_choose_best_result_prefers_exact_problem_id():
    results = [
        ProblemSearchResult(1, "P1001", "相似题", 0, [], None, None),
        ProblemSearchResult(2, "GESP251203T2", "目标题", 0, [], None, None),
    ]

    selected = choose_best_result(results, " gesp251203t2 ")

    assert selected == results[1]


def test_render_markdown_includes_detail_sections_and_clean_examples():
    result = ProblemSearchResult(
        pid=4699,
        problem_id="GESP251203T2",
        title="[GESP 三级]小杨的智慧购物",
        difficulty=0,
        tags=["数组"],
        total=249,
        ac=94,
    )
    detail = {
        "description": "题面",
        "input": "输入说明",
        "output": "输出说明",
        "examples": "<input>2 5\n1 1</input><output>4</output>",
        "hint": "提示",
    }

    markdown = render_markdown(result, detail)

    assert "# GESP251203T2 [GESP 三级]小杨的智慧购物" in markdown
    assert "- 标签: 数组" in markdown
    assert "## 题意\n\n题面" in markdown
    assert "输入：\n2 5\n1 1" in markdown
    assert "输出：\n4" in markdown
