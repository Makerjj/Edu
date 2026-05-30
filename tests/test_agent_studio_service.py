import json

import pytest

from src.agent_studio.service import create_agent_run, list_agent_runs


def test_create_agent_run_writes_replayable_plan_and_trace(tmp_path):
    record = create_agent_run(
        {
            "title": "GESP 四级 map/set 教学包",
            "goal": "生成题单、备课方案并进入审计。",
            "outputs": ["question_pack.generate", "lesson_plan.generate"],
            "evidenceQueries": ["GESP 四级 map", "小杨的字典"],
            "auditLevel": "strict",
        },
        tmp_path,
    )

    run_dir = tmp_path / record["runId"]
    assert (run_dir / "input.json").exists()
    assert (run_dir / "workflow_plan.json").exists()
    assert (run_dir / "trace.jsonl").exists()
    assert record["status"] == "planned"
    assert record["workflow"][0]["step"] == "retrieve_evidence"

    trace = json.loads((run_dir / "trace.jsonl").read_text(encoding="utf-8"))
    assert trace["event"] == "run_planned"
    assert list_agent_runs(tmp_path)[0]["runId"] == record["runId"]


def test_create_agent_run_requires_outputs(tmp_path):
    with pytest.raises(ValueError, match="至少选择一个输出产物"):
        create_agent_run(
            {
                "title": "任务",
                "goal": "目标",
                "outputs": [],
                "evidenceQueries": [],
            },
            tmp_path,
        )
