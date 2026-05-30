from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AGENT_TOOL_REGISTRY = [
    {
        "id": "problem_bank.search",
        "name": "题库检索",
        "description": "按题号或关键词检索 OJ/GESP 题目，并返回可引用的题面 Markdown。",
        "status": "connected",
    },
    {
        "id": "question_pack.generate",
        "name": "专题题单生成",
        "description": "基于证据生成题目版和解析版，后续接入独立审计。",
        "status": "planned",
    },
    {
        "id": "lesson_plan.generate",
        "name": "备课方案生成",
        "description": "根据主题、学情和材料生成可审计的 lesson_spec。",
        "status": "planned",
    },
    {
        "id": "video.workflow",
        "name": "课件/视频工作流",
        "description": "调用 pre_lesson 的 check、frames、draft、final gate。",
        "status": "planned",
    },
    {
        "id": "audit.run",
        "name": "质量审计",
        "description": "记录确定性检查、LLM 审计和人工确认结果。",
        "status": "planned",
    },
]


@dataclass(frozen=True)
class AgentRunRequest:
    title: str
    goal: str
    outputs: list[str]
    evidence_queries: list[str]
    audit_level: str = "strict"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_list(values: list[Any], limit: int = 12) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def normalize_run_request(payload: dict[str, Any]) -> AgentRunRequest:
    title = str(payload.get("title") or "").strip()
    goal = str(payload.get("goal") or "").strip()
    outputs = _clean_list(payload.get("outputs") or [])
    evidence_queries = _clean_list(payload.get("evidenceQueries") or [])
    audit_level = str(payload.get("auditLevel") or "strict").strip() or "strict"
    if not title:
        raise ValueError("请填写任务名称")
    if not goal:
        raise ValueError("请填写任务目标")
    if not outputs:
        raise ValueError("请至少选择一个输出产物")
    return AgentRunRequest(
        title=title,
        goal=goal,
        outputs=outputs,
        evidence_queries=evidence_queries,
        audit_level=audit_level,
    )


def create_agent_run(payload: dict[str, Any], runs_dir: Path) -> dict[str, Any]:
    request = normalize_run_request(payload)
    run_id = uuid.uuid4().hex[:12]
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    created_at = utc_now()
    tool_ids = [tool["id"] for tool in AGENT_TOOL_REGISTRY]
    workflow = [
        {"step": "retrieve_evidence", "status": "pending", "tools": ["problem_bank.search"]},
        {"step": "plan_outputs", "status": "pending", "tools": ["lesson_plan.generate"]},
        {"step": "generate_artifacts", "status": "pending", "tools": request.outputs},
        {"step": "audit", "status": "pending", "tools": ["audit.run"]},
        {"step": "human_approval", "status": "pending", "tools": []},
    ]
    record = {
        "runId": run_id,
        "createdAt": created_at,
        "status": "planned",
        "title": request.title,
        "goal": request.goal,
        "outputs": request.outputs,
        "evidenceQueries": request.evidence_queries,
        "auditLevel": request.audit_level,
        "toolRegistry": tool_ids,
        "workflow": workflow,
        "artifacts": {
            "input": "input.json",
            "trace": "trace.jsonl",
            "plan": "workflow_plan.json",
        },
    }
    (run_dir / "input.json").write_text(
        json.dumps(
            {
                "title": request.title,
                "goal": request.goal,
                "outputs": request.outputs,
                "evidenceQueries": request.evidence_queries,
                "auditLevel": request.audit_level,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "workflow_plan.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (run_dir / "trace.jsonl").write_text(
        json.dumps(
            {
                "event": "run_planned",
                "runId": run_id,
                "createdAt": created_at,
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return record


def list_agent_runs(runs_dir: Path, limit: int = 20) -> list[dict[str, Any]]:
    if not runs_dir.exists():
        return []
    records: list[dict[str, Any]] = []
    for plan_path in sorted(runs_dir.glob("*/workflow_plan.json"), reverse=True):
        try:
            record = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records.append(record)
        if len(records) >= limit:
            break
    return records
