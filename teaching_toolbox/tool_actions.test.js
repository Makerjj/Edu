const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const appSource = fs.readFileSync(path.join(__dirname, "app.js"), "utf8");
const htmlSource = fs.readFileSync(path.join(__dirname, "index.html"), "utf8");
const cssSource = fs.readFileSync(path.join(__dirname, "styles.css"), "utf8");
const functionMatch = appSource.match(/function updateToolActions\(\) \{[\s\S]*?\n\}/);

assert.match(
  appSource,
  /const previousTeamId = teamSelect\.value[\s\S]*?if \(teamSelect\.value\) \{\s*teamSelect\.dispatchEvent\(new Event\("change"\)\)/,
  "a restored team selection should trigger training loading after teams are refreshed",
);
assert.match(
  appSource,
  /restoreDraft\(\);\s*if \(tool === "profile" && teamSelect\.value\) \{\s*teamSelect\.dispatchEvent\(new Event\("change"\)\)/,
  "switching to the report page should load trainings for the restored team",
);

assert.ok(functionMatch, "updateToolActions should exist");
assert.match(appSource, /let currentTool = "feedback"/, "the toolbox should open on the feedback page");
assert.match(
  htmlSource,
  /<h2 id="toolTitle">课后反馈<\/h2>/,
  "the initial page title should match the feedback page",
);
assert.match(
  htmlSource,
  /<button class="nav-button active" data-tool="feedback"/,
  "the feedback nav item should be active on first load",
);
assert.match(
  htmlSource,
  /id="compressKnowledgeBtn"[\s\S]*?>压缩知识点<\/button>/,
  "the feedback page should expose a compact knowledge-point action",
);
assert.doesNotMatch(
  cssSource,
  /knowledge-image-preview[\s\S]*inset:\s*1px/,
  "the screenshot preview should not stretch across the whole knowledge input shell",
);
assert.match(
  htmlSource,
  /textarea name="knowledgePoints" rows="3"/,
  "the knowledge-point input should use a smaller textarea",
);
const knowledgeShell = htmlSource.match(/id="feedbackKnowledgeShell"[\s\S]*?<\/textarea>/)[0];
assert.ok(knowledgeShell.indexOf('id="feedbackScreenshotPreview"') < knowledgeShell.indexOf('<textarea'),
  "the image attachment should appear above the text inside the same input shell");
assert.match(cssSource, /\.knowledge-image-frame img\s*\{[^}]*width:\s*64px;[^}]*height:\s*64px;[^}]*object-fit:\s*cover;/,
  "attachments should keep a stable 64px thumbnail for every image aspect ratio");
assert.match(cssSource, /\.knowledge-input-shell:focus-within\s*\{/,
  "the shared input shell should show the focus state");
assert.match(
  appSource,
  /feedback-dimension-grid[\s\S]*understanding[\s\S]*independence[\s\S]*classroomState[\s\S]*mainIssue/,
  "each feedback card should expose the configured evaluation dimensions",
);
assert.match(
  appSource,
  /includeInFeedback|写入反馈|generateFeedbackForStudent|feedbackStudentsState/,
  "feedback cards should support include toggles and persisted student state",
);
assert.match(
  appSource,
  /课堂细节描述[\s\S]*feedback-details-input[\s\S]*student\.details/,
  "each feedback card should accept and persist concrete classroom details",
);
assert.match(
  appSource,
  /details:\s*student\.details\s*\|\|\s*""/,
  "feedback generation should send concrete classroom details to the agent",
);
assert.doesNotMatch(
  appSource.match(/postJson\("\/api\/feedback\/generate"[\s\S]*?\n\s*\}\);/)?.[0] || "",
  /knowledgePoints|topic:/,
  "private feedback generation should not depend on the separate lesson-content fields",
);
assert.match(
  htmlSource,
  /截图仅用于整理课堂内容，可不上传；学生私人反馈根据下方表现和细节单独生成/,
  "the UI should make the screenshot and private-feedback boundary explicit",
);
assert.doesNotMatch(
  appSource.match(/async function generateFeedbackForStudent[\s\S]*?\n\}/)?.[0] || "",
  /正在交给 Codex agent 生成反馈|反馈已生成，可继续手动微调后再检查/,
  "private feedback generation should write directly into the feedback textarea without an extra status panel",
);
assert.doesNotMatch(
  appSource.match(/function generateOutput\(\) \{[\s\S]*?\n\}/)?.[0] || "",
  /renderFeedbackList\(/,
  "typing inside a feedback card must not rebuild the card and steal focus",
);
assert.match(
  appSource,
  /form\.id === "feedbackForm" && event\.target\.closest\("#feedbackList"\)/,
  "feedback-card fields should bypass the parent form's generic input handler",
);
assert.match(
  appSource,
  /restoreFeedbackStudentsState\(\);\s*renderFeedbackList\(\);/,
  "restored students should be rendered immediately after a page refresh",
);
assert.match(
  appSource,
  /和 Agent 沟通修改[\s\S]*发送并修改[\s\S]*\/api\/feedback\/revise/,
  "each student card should support iterative feedback revision through the local agent",
);
assert.match(
  cssSource,
  /--accent:\s*#006bff[\s\S]*\.feedback-card[\s\S]*border-radius:\s*12px[\s\S]*\.feedback-revise-button[\s\S]*background:\s*var\(--accent\)/,
  "feedback cards should follow the local DESIGN.md tokens and primary-action hierarchy",
);
assert.match(
  cssSource,
  /\.sidebar[\s\S]*background:\s*#ffffff[\s\S]*\.nav-button\.active[\s\S]*background:\s*var\(--accent-soft\)/,
  "the sidebar should use the quiet light DESIGN.md navigation treatment",
);
assert.doesNotMatch(
  htmlSource,
  /当前边界|网页是统一入口/,
  "the sidebar should not contain a large internal implementation note",
);
assert.match(
  htmlSource,
  /id="themeToggleBtn"[\s\S]*aria-pressed="false"[\s\S]*id="themeToggleText"/,
  "the toolbox should expose an accessible theme toggle",
);
assert.match(
  appSource,
  /themeState[\s\S]*restoreTheme\(\)[\s\S]*toggleTheme[\s\S]*localStorage\.setItem\(themeState/,
  "the selected theme should persist across refreshes",
);
assert.match(
  cssSource,
  /\[data-theme="dark"\][\s\S]*--background-100:\s*#000000[\s\S]*--gray-1000:\s*#ededed[\s\S]*--blue-700:\s*#006efe/,
  "dark mode should use the DESIGN.dark.md semantic token values",
);
assert.match(
  cssSource,
  /\.sidebar-resize-handle\s*\{[\s\S]*background:\s*transparent[\s\S]*\.sidebar-resize-handle::before[\s\S]*width:\s*1px[\s\S]*background:\s*var\(--line\)/,
  "the resize handle should remain usable without showing a heavy vertical track",
);
assert.match(
  appSource,
  /feedback-result-label[\s\S]*私人反馈/,
  "the generated private-feedback field should have a clear visual label",
);
assert.match(
  appSource,
  /generateBtn\.textContent = "反馈"/,
  "each feedback card should expose a feedback action that triggers agent generation",
);
assert.match(
  appSource,
  /setFeedbackStatus\(`正在为.*生成反馈/ ,
  "feedback generation should surface a visible running status while the agent is working",
);
assert.doesNotMatch(
  htmlSource,
  /data-tool="service"|data-tool-view="service"|课后服务话术/,
  "the duplicated after-class service tool should not be visible",
);
assert.doesNotMatch(
  appSource,
  /service:\s*\{|buildServiceScript/,
  "the duplicated after-class service tool should not be registered",
);
assert.match(
  functionMatch[0],
  /userMenu\.hidden\s*=\s*!needsOj\s*\|\|\s*!isLoggedIn/,
  "non-OJ pages should hide the OJ account menu even after login",
);
assert.match(
  appSource,
  /setReportStatus\("Excel 文件已生成，下载已触发。", "success", REPORT_SUCCESS_HIDE_MS\)/,
  "the generated Excel success status should be a temporary completion notice",
);
const reportFunction = appSource.match(/async function generateReport\(\) \{[\s\S]*?\n\}/)[0];
assert.match(reportFunction, /renderReportResult\(result\)/, "generation should show an editable web table");
assert.doesNotMatch(reportFunction, /link\.click|document\.createElement\("a"\)/, "generation must not start a download");
assert.match(appSource, /postJson\("\/api\/reports\/export"/, "downloads should submit current table edits");
assert.match(htmlSource, /id="downloadReportBtn"/, "the result should retain an Excel download action");
assert.match(
  appSource,
  /window\.setTimeout\(\(\) => \{[\s\S]*clearReportStatus\(\);[\s\S]*\}, autoHideMs\)/,
  "report status should support auto-hiding temporary success messages",
);

console.log("tool action visibility tests passed");
