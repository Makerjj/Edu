import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import video_workflow


class StoryboardValidationTest(unittest.TestCase):
    def test_load_storyboard_requires_shots_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            (project_dir / "storyboard.json").write_text('{"shots": {}}', encoding="utf-8")

            findings = video_workflow.validate_storyboard(project_dir)

        self.assertEqual(findings, ["storyboard.json field `shots` must be a non-empty list"])

    def test_load_storyboard_rejects_duplicate_ids_and_missing_subtitles(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            storyboard = {
                "shots": [
                    {
                        "id": "intro-01",
                        "scene": "intro",
                        "title": "开场",
                        "visual": "显示题目",
                        "narration": "今天讲密码判断。",
                        "subtitle": "今天讲密码判断。",
                    },
                    {
                        "id": "intro-01",
                        "scene": "intro",
                        "title": "重复",
                        "visual": "继续显示题目",
                        "narration": "重复的分镜编号。",
                    },
                ]
            }
            (project_dir / "storyboard.json").write_text(json.dumps(storyboard), encoding="utf-8")

            findings = video_workflow.validate_storyboard(project_dir)

        self.assertEqual(
            findings,
            [
                "shot intro-01 duplicates a previous shot id",
                "shot intro-01 missing required field: subtitle",
            ],
        )

    def test_valid_storyboard_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            storyboard = {
                "shots": [
                    {
                        "id": "sample-01",
                        "scene": "sample",
                        "title": "样例输入",
                        "visual": "左侧样例输入，右侧样例输出。",
                        "narration": "先看样例输入。",
                        "subtitle": "先看样例输入。",
                        "durationHint": 6,
                        "checks": ["样例完整"],
                    }
                ]
            }
            (project_dir / "storyboard.json").write_text(json.dumps(storyboard), encoding="utf-8")

            findings = video_workflow.validate_storyboard(project_dir)

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
