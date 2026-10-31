import base64
import subprocess
from pathlib import Path

import pytest

from teaching_toolbox import server
from src.xdf_report.matcher import MatchError


def test_static_assets_disable_browser_cache():
    source = Path(server.__file__).read_text(encoding="utf-8")
    assert 'self.send_header("Cache-Control", "no-store")' in source


def test_decode_feedback_image_rejects_non_data_url():
    with pytest.raises(MatchError, match="请上传图片截图"):
        server.decode_feedback_image({"imageData": "not-image"})


def test_summarize_feedback_image_uses_codex_agent(monkeypatch, tmp_path):
    image_bytes = b"\x89PNG\r\n\x1a\nfake"
    payload = {
        "imageData": "data:image/png;base64,"
        + base64.b64encode(image_bytes).decode("ascii")
    }
    calls = {}

    def fake_run(args, check, capture_output, text, timeout, input):
        calls["args"] = args
        calls["input"] = input

        class Result:
            stdout = (
                '{"topic":"大数加减法",'
                '"knowledgePoints":"#沟通称呼语#～本周课程主要讲了“大数加减法”这一模块内容。\\n\\n'
                '本节课主要内容如下：\\n1. 整数范围：位、字节、整型溢出。\\n'
                '2. 高精度数存储：数组或字符串存储大整数。\\n\\n'
                '本节课的重难点是理解进位/借位的本质。\\n\\n'
                '课后可以重点复习数组倒序存储和逐位计算。",'
                '"summary":"本节课围绕大数加减法进行学习。"}'
            )
            stderr = ""

        return Result()

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    monkeypatch.setattr(server.tempfile, "TemporaryDirectory", lambda: _TempDir(tmp_path))
    monkeypatch.setattr(
        server,
        "load_feedback_skill_excerpt",
        lambda: "## 【本节课学了什么】\n本节课主要内容如下\n本节课的重难点是\n孩子课后这样复习",
    )

    result = server.summarize_feedback_image_with_codex(payload)

    assert result == {
        "topic": "大数加减法",
        "knowledgePoints": (
            "#沟通称呼语#～本周课程主要讲了“大数加减法”这一模块内容。\n\n"
            "本节课主要内容如下：\n1. 整数范围：位、字节、整型溢出。\n"
            "2. 高精度数存储：数组或字符串存储大整数。\n\n"
            "本节课的重难点是理解进位/借位的本质。\n\n"
            "课后可以重点复习数组倒序存储和逐位计算。"
        ),
        "summary": "本节课围绕大数加减法进行学习。",
    }
    assert calls["args"][:4] == [
        "/opt/homebrew/bin/codex",
        "exec",
        "--skip-git-repo-check",
        "--image",
    ]
    assert calls["args"][-1] == "-"
    assert "请观察这张课堂截图" in calls["input"]
    assert "完整知识点反馈文本" in calls["input"]
    assert "本节课主要内容如下" in calls["input"]
    assert "参考本地课后反馈写作 skill" in calls["input"]
    assert "【本节课学了什么】" in calls["input"]
    assert "本节课的重难点是" in calls["input"]
    assert "不要输出孩子表现分档" in calls["input"]


def test_summarize_feedback_image_reports_codex_failure(monkeypatch, tmp_path):
    payload = {
        "imageData": "data:image/png;base64,"
        + base64.b64encode(b"fake image").decode("ascii")
    }

    def fake_run(args, check, capture_output, text, timeout, input):
        raise subprocess.CalledProcessError(
            1,
            args,
            output="",
            stderr="not logged in",
        )

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    monkeypatch.setattr(server.tempfile, "TemporaryDirectory", lambda: _TempDir(tmp_path))

    with pytest.raises(MatchError, match="Codex agent 总结失败：not logged in"):
        server.summarize_feedback_image_with_codex(payload)


def test_check_feedback_text_uses_skill_checklist(monkeypatch):
    calls = {}

    def fake_run(args, check, capture_output, text, timeout, input):
        calls["args"] = args
        calls["input"] = input

        class Result:
            stdout = (
                '{"status":"needs_fix",'
                '"issues":[{"type":"name","severity":"high","message":"出现真实学生名朱文宇","quote":"朱文宇同学"}],'
                '"suggestions":["把真实姓名替换成 #学员昵称#"],'
                '"summary":"发现 1 个高风险问题"}'
            )
            stderr = ""

        return Result()

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    monkeypatch.setattr(
        server,
        "load_feedback_skill_excerpt",
        lambda: "## 检查清单\n1. 是否所有姓名都替换成 #学员昵称#\n2. 是否没有编造课堂表现",
    )

    result = server.check_feedback_text_with_codex(
        {
            "studentName": "朱文宇",
            "username": "SZS3386729021",
            "level": "优秀",
            "topic": "二分查找",
            "feedback": "朱文宇同学这节课表现非常棒，作业全部完成。",
        }
    )

    assert result["status"] == "needs_fix"
    assert result["issues"][0]["type"] == "name"
    assert result["issues"][0]["severity"] == "high"
    assert result["suggestions"] == ["把真实姓名替换成 #学员昵称#"]
    assert calls["args"] == [
        "/opt/homebrew/bin/codex",
        "exec",
        "--skip-git-repo-check",
        "-",
    ]
    assert "课后反馈质检员" in calls["input"]
    assert "朱文宇" in calls["input"]
    assert "SZS3386729021" in calls["input"]
    assert "检查清单" in calls["input"]
    assert "真实学生名" in calls["input"]
    assert "错别字" in calls["input"]
    assert "JSON" in calls["input"]


def test_generate_feedback_with_codex_uses_selected_dimensions(monkeypatch):
    calls = {}

    def fake_run(args, check, capture_output, text, timeout, input):
        calls["args"] = args
        calls["input"] = input

        class Result:
            stdout = "#沟通称呼语#～本节课我们学习了数组与循环。\n\n#学员昵称#同学这节课能够在提示后完成主要步骤，课堂状态比较稳定。\n\n课后可以继续巩固边界条件～"
            stderr = ""

        return Result()

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    monkeypatch.setattr(
        server,
        "load_feedback_skill_excerpt",
        lambda: "## 版本规则\n- 中等版\n## 证据边界\n不要编造课堂表现",
    )

    result = server.generate_feedback_with_codex(
        {
            "studentName": "朱文宇",
            "username": "SZS3386729021",
            "details": "提问到循环边界时能够说出右端点要单独检查，代码部分在提示后完成。",
            "level": "中等",
            "dimensions": {
                "understanding": {"value": "初步理解", "include": False},
                "independence": {"value": "提示后完成", "include": True},
                "classroomState": {"value": "比较稳定", "include": True},
                "mainIssue": {"value": "边界条件", "include": True},
            },
        }
    )

    assert result["feedback"].startswith("#沟通称呼语#")
    assert calls["args"] == [
        "/opt/homebrew/bin/codex",
        "exec",
        "--skip-git-repo-check",
        "-",
    ]
    assert "只使用 include=true 的维度" in calls["input"]
    assert "提示后完成" in calls["input"]
    assert "比较稳定" in calls["input"]
    assert "边界条件" in calls["input"]
    assert "右端点要单独检查" in calls["input"]
    assert "课堂细节描述属于用户明确提供的学生表现证据" in calls["input"]
    assert "课堂内容反馈与学生私人反馈是两个独立对象" in calls["input"]
    assert "不得因为没有上传课堂截图而拒绝生成" in calls["input"]
    assert "初步理解" in calls["input"]
    assert '"include": false' in calls["input"].lower()


def test_generate_private_feedback_does_not_require_lesson_content(monkeypatch):
    def fake_run(args, check, capture_output, text, timeout, input):
        class Result:
            stdout = "#沟通称呼语#，#学员昵称#同学课堂状态比较稳定，后续继续保持练习节奏就可以啦～"
            stderr = ""

        return Result()

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    monkeypatch.setattr(server, "load_feedback_skill_excerpt", lambda: "私聊反馈使用自然段")

    result = server.generate_feedback_with_codex(
        {
            "studentName": "测试学生",
            "level": "中等",
            "details": "",
            "dimensions": {
                "classroomState": {"value": "比较稳定", "include": True},
            },
        }
    )

    assert "#学员昵称#同学" in result["feedback"]


def test_revise_feedback_with_codex_uses_skill_and_instruction(monkeypatch):
    calls = {}

    def fake_run(args, check, capture_output, text, timeout, input):
        calls["input"] = input

        class Result:
            stdout = '{"message":"已压缩并调整语气。","feedback":"#沟通称呼语#，#学员昵称#同学本节课状态认真，后续继续巩固即可～"}'
            stderr = ""

        return Result()

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    monkeypatch.setattr(server, "load_feedback_skill_excerpt", lambda: "私聊反馈使用自然段")
    result = server.revise_feedback_with_codex(
        {
            "feedback": "#沟通称呼语#，#学员昵称#同学这节课表现较好。",
            "instruction": "再简短一点，语气自然些",
            "details": "课堂状态认真",
            "level": "中等",
            "dimensions": {},
        }
    )

    assert result["message"] == "已压缩并调整语气。"
    assert "#学员昵称#同学" in result["feedback"]
    assert "再简短一点" in calls["input"]
    assert "after-class-feedback skill" in calls["input"]


class _TempDir:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return str(self.path)

    def __exit__(self, exc_type, exc, tb):
        return False
