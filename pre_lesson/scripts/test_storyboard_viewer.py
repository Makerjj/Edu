import unittest
from pathlib import Path


VIEWER = Path(__file__).resolve().parent.parent / "remotion_password_judgement" / "storyboard_viewer.html"


class StoryboardViewerStructureTest(unittest.TestCase):
    def test_viewer_uses_design_tokens_and_workbench_regions(self):
        html = VIEWER.read_text(encoding="utf-8")

        for token in [
            "--background-100",
            "--background-200",
            "--gray-1000",
            "--gray-alpha-400",
            "--blue-700",
            "--radius-sm",
            "--space-4",
        ]:
            self.assertIn(token, html)

        for region in [
            'class="workspace-shell"',
            'class="shot-rail"',
            'class="script-panel"',
            'class="review-rail"',
        ]:
            self.assertIn(region, html)

        for label in ["字幕文本", "旁白脚本", "画面说明", "检查点", "字段状态"]:
            self.assertIn(label, html)


if __name__ == "__main__":
    unittest.main()
