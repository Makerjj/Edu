from src.problem_bank.service import ProblemBankSearch, search_problem_bank


class FakeClient:
    def get(self, path, params):
        if path == "/get-problem-list":
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
        if path == "/get-problem-detail":
            return {
                "data": {
                    "problem": {
                        "description": "题面",
                        "input": "输入说明",
                        "output": "输出说明",
                    }
                }
            }
        raise AssertionError(path)


def test_search_problem_bank_returns_markdown_detail():
    result = search_problem_bank(
        FakeClient(),
        ProblemBankSearch(query="小杨", limit=30, include_detail=True),
    )

    assert result["query"] == "小杨"
    assert result["limit"] == 20
    assert result["count"] == 1
    assert result["items"][0]["problemId"] == "GESP251203T2"
    assert "## 题意\n\n题面" in result["items"][0]["markdown"]
