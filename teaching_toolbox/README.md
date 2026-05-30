# 教学工具箱

本目录是教学工具箱的本地 Web 应用，用来把常用教学工作流先做成本地可用的网页工具。

## 当前功能

- 登录：使用 OJ 手机号和密码登录，登录状态保存在本地 SQLite。
- 学情反馈表：选择团队、训练、课堂题目、课后题目和学生后生成 Excel。
- 题库检索：按题号或关键词检索 OJ/GESP 题目，可拉取题面 Markdown。
- 课后服务话术：按沟通场景和学生表现生成家长私聊话术。
- 课前备课：按主题、学情、重点难点和材料生成备课框架。
- Agent 工作台：维护工具注册表，创建可追踪的 run 计划和本地 trace。

## 本地使用

需要启动后端服务：

```bash
python3 server.py
```

然后访问：

```text
http://127.0.0.1:8765
```

登录数据保存在：

```text
teaching_toolbox/.data/toolbox.sqlite3
teaching_toolbox/.data/secret.key
```

`.data/`、`.generated/` 和 `.agent_runs/` 已加入 `.gitignore`，不要提交到 GitHub。

## 后续扩展

建议按这个顺序加功能：

1. 把专题题单生成和独立审计接入 Agent 工作台。
2. 给 Agent run 增加真实工具调用结果、失败原因和人工确认节点。
3. 接入课件/视频 workflow，但网页只创建任务和查看关键帧/审计报告。
