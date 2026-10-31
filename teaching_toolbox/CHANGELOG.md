# 教学工具箱变更记录

## 2026-10-18

- 文件：`teaching_toolbox/app.js`、`teaching_toolbox/tool_actions.test.js`。修复进入页面或切换到学情表后团队下拉框保留选中值、训练名称未触发加载的问题；恢复团队选项或学情表草稿后补发 `change` 事件，训练名称会重新加载并可选择。
- 验证：`node --check teaching_toolbox/app.js`、`node teaching_toolbox/tool_actions.test.js`。
- 结果：JavaScript 语法检查和页面行为检查通过。

- 文件：`src/xdf_report/report_data.py`、`tests/test_report_data.py`。学情表成绩单元格显示已提交的 PAC、WA；AC 继续显示 ✅，未提交保持空白。PAC 使用明确状态或正分识别。
- 验证：`PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_report_data.py tests/test_teaching_toolbox_reports.py`。
- 结果：修改后测试通过；基线结果为 19 项通过。

## 2026-09-26

- 修复暗色模式下课后反馈页面的可读性：提高表单标签、说明文字和学生账号信息的亮度，增加输入区与反馈卡片的背景层次，并补充按钮的暗色状态。
- 验证方式：浏览器检查暗色主题的文字、卡片背景、占位文字和输入框边界；`node tool_actions.test.js` 通过。`node feedback_builder.test.js` 的学生数断言预期 6 人、当前 7 人，属于现有测试数据差异。

## 2026-06-24

- 缩小“本节知识点”输入框，并新增“压缩知识点”按钮。
- 每个学生的反馈卡片改为多维度表现选项，包括理解、独立、课堂状态和主要问题。
- 删除左侧导航中的“课后服务话术”入口。
- 删除对应前端表单和预览生成逻辑，避免与“课后反馈”重复。
- 更新工具箱说明文档和导航测试。
## 2026-10-14

- 文件：`index.html`、`app.js`、`report_exit.test.js`。增加“退出学情表”按钮，关闭预览并返回表单，保留选择与表格编辑。验证：退出状态测试、原报表响应测试、JavaScript 语法检查。

- 需求修正：作业类型表头改为“本次作业完成情况”，名单区隐藏请假控件。测试覆盖预览与导出列数、表头、请假及星星内容缺席；常规类型保持原有结构。

- 文件：`index.html`、`app.js`、`server.py`、`src/xdf_report/cli.py`、`tests/test_teaching_toolbox_reports.py`
- 修改内容：增加“课后作业完成情况”表格类型。该类型复用当前训练题目作为作业题，生成时使用姓名与“课后作业”区域，不显示课堂表现、出勤和课堂作业列；常规类型保持原流程。
- 验证方式：`PYTHONPATH=. .venv/bin/python -m pytest tests/test_excel_template.py tests/test_teaching_toolbox_reports.py -q`；`node --check teaching_toolbox/app.js`
- 验证结果：报表、命令行和成绩处理回归共 48 项通过；JavaScript 语法检查通过。浏览器核验类型切换、作业题标签和常规课后题区域隐藏。新类型忽略请假标记，文件名以“课后作业完成情况”区分。

## 2026-10-31

- 文件：`app.js`、`styles.css`、`report_response.test.js`。
- 现象与根因：题目多时，列最小宽度及表格 70vh 高度上限产生横纵滚动条，截图缺少表格内容。
- 修改内容：表格按窗口宽高缩放；移除表格和编辑框的滚动限制；窗口变化、侧栏宽度变化与内容编辑后重新计算缩放。
- 验证方式：浏览器检查 26 列、20/60 行模拟学生数据、合并表头、多行编辑及 800×600 窗口；四项相关 Node 回归；语法检查；补丁重建与副本回滚。
- 验证结果：修改后全表在视口内，无横纵滚动；编辑保留；回滚恢复原行为且哈希相同；相关回归通过。
- 已知限制：列数或行数增加会缩小字号；反馈生成器现有 7 与 6 的人数断言差异未改动。
- 记录与恢复：`../change_artifacts/2026-10-31-report-fit/`。

### 2026-10-31 删除题库检索

- 文件：`index.html`、`app.js`、`README.md`。
- 修改内容：移除“题库检索”导航、页面、工具注册、检索及结果渲染逻辑和事件绑定；移除功能说明。
- 验证方式：浏览器检查删除前、修改后与回滚副本的导航和页面切换；四项相关回归、语法检查、补丁重建及回滚哈希检查。
- 验证结果：修改后导航包含“学情反馈表”和“课后反馈”，两页切换通过；回滚恢复三个入口；四项回归通过。
- 恢复记录：沿用 `../change_artifacts/2026-10-31-report-fit/` 中的四个交付角色。

### 2026-10-31 GitHub 更新

- 范围：教学工具箱当前页面、报表服务及其运行依赖和测试。
- 修改内容：发布学情表完整显示、移除题库检索，并补齐当前工具箱需要的配套代码。
- 验证方式：在 GitHub main 当前提交创建的隔离目录运行 Python 报表与工具箱测试、前端回归、JavaScript 语法检查及差异格式检查。
- 验证结果：84 项 Python 测试、4 项前端回归通过；语法与差异格式检查通过。
