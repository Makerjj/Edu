const toolMeta = {
  profile: {
    title: "学情反馈表",
    formId: "profileForm",
    build: buildProfileFeedback,
  },
  service: {
    title: "课后服务话术",
    formId: "serviceForm",
    build: buildServiceScript,
  },
  prep: {
    title: "课前备课",
    formId: "prepForm",
    build: buildLessonPrep,
  },
};

let currentTool = "profile";
let latestOutput = "";

const toolTitle = document.querySelector("#toolTitle");
const navButtons = document.querySelectorAll(".nav-button");
const toolViews = document.querySelectorAll("[data-tool-view]");
const teamSelect = document.querySelector("#teamSelect");
const trainingSelect = document.querySelector("#trainingSelect");
const problemList = document.querySelector("#problemList");
const problemStatus = document.querySelector("#problemStatus");
const problemsInput = document.querySelector("#problemsInput");
const afterProblemList = document.querySelector("#afterProblemList");
const afterProblemStatus = document.querySelector("#afterProblemStatus");
const afterProblemsInput = document.querySelector("#afterProblemsInput");
const studentList = document.querySelector("#studentList");
const studentStatus = document.querySelector("#studentStatus");
const studentsFilenameInput = document.querySelector("#studentsFilenameInput");
const studentsJsonInput = document.querySelector("#studentsJsonInput");
const saveStudentsBtn = document.querySelector("#saveStudentsBtn");
const teamNameInput = document.querySelector("#teamNameInput");
const teamIdInput = document.querySelector("#teamIdInput");
const trainingTitleInput = document.querySelector("#trainingTitleInput");
const trainingIdInput = document.querySelector("#trainingIdInput");
const reportStatus = document.querySelector("#reportStatus");
const generateReportBtn = document.querySelector("#generateReportBtn");

function getFormData(formId) {
  const form = document.querySelector(`#${formId}`);
  return Object.fromEntries(new FormData(form).entries());
}

function clean(value, fallback = "待补充") {
  const text = String(value || "").trim();
  return text || fallback;
}

function sentenceJoin(parts) {
  return parts.filter(Boolean).join("\n\n");
}

function shellQuote(value) {
  const text = String(value || "");
  return `'${text.replace(/'/g, `'\\''`)}'`;
}

function addCliArg(args, flag, value) {
  const text = String(value || "").trim();
  if (!text) return;
  args.push(flag, shellQuote(text));
}

async function fetchJson(url) {
  const response = await fetch(url);
  const payload = await readJsonResponse(response);
  if (!response.ok) {
    throw new Error(payload.error || `请求失败：${response.status}`);
  }
  return payload;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await readJsonResponse(response);
  if (!response.ok) {
    throw new Error(payload.error || `请求失败：${response.status}`);
  }
  return payload;
}

async function readJsonResponse(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch (_error) {
    const preview = text.trim().slice(0, 80) || "空响应";
    throw new Error(`服务器返回的不是 JSON：${preview}`);
  }
}

function option(label, value) {
  const item = document.createElement("option");
  item.textContent = label;
  item.value = value;
  return item;
}

function setSelectOptions(select, items, placeholder) {
  select.replaceChildren(option(placeholder, ""));
  items.forEach((item) => select.appendChild(item));
}

function setProblemStatus(message) {
  problemStatus.textContent = message;
}

function setAfterProblemStatus(message) {
  afterProblemStatus.textContent = message;
}

function setStudentStatus(message) {
  studentStatus.textContent = message;
}

async function loadTeams() {
  try {
    const payload = await fetchJson("/api/teams");
    const options = payload.teams.map((team) =>
      option(`${team.name}（gid=${team.groupId}）`, String(team.groupId)),
    );
    setSelectOptions(teamSelect, options, "请选择团队");
    setProblemStatus(`已加载 ${payload.teams.length} 个团队`);
  } catch (error) {
    setSelectOptions(teamSelect, [], "团队加载失败");
    setProblemStatus(error.message);
  }
}

async function loadTrainings(groupId) {
  trainingSelect.disabled = true;
  setSelectOptions(trainingSelect, [], "训练加载中...");
  problemList.replaceChildren();
  afterProblemList.replaceChildren();
  problemsInput.value = "";
  afterProblemsInput.value = "";
  setProblemStatus("训练加载中...");
  setAfterProblemStatus("训练加载中...");
  if (!groupId) {
    setSelectOptions(trainingSelect, [], "请先选择团队");
    setProblemStatus("请选择训练后加载题目");
    setAfterProblemStatus("请选择训练后加载课后题");
    generateOutput();
    return;
  }

  try {
    const payload = await fetchJson(`/api/trainings?groupId=${encodeURIComponent(groupId)}`);
    const options = payload.trainings.map((training) =>
      option(training.title, String(training.trainingId)),
    );
    setSelectOptions(trainingSelect, options, "请选择训练");
    trainingSelect.disabled = false;
    setProblemStatus(`已加载 ${payload.trainings.length} 个训练`);
    setAfterProblemStatus("请选择训练后加载课后题");
  } catch (error) {
    setSelectOptions(trainingSelect, [], "训练加载失败");
    setProblemStatus(error.message);
    setAfterProblemStatus(error.message);
  }
  generateOutput();
}

async function loadStudents(groupId) {
  studentList.replaceChildren();
  if (!groupId) {
    setStudentStatus("请选择团队后加载学生");
    return;
  }

  setStudentStatus("学生加载中...");
  try {
    const payload = await fetchJson(`/api/students?groupId=${encodeURIComponent(groupId)}`);
    renderStudentRows(payload.students || []);
    setStudentStatus(`已加载 ${payload.students.length} 名学生，可勾选并修改 real_name`);
  } catch (error) {
    setStudentStatus(error.message);
  }
}

async function loadProblems(trainingId) {
  problemList.replaceChildren();
  afterProblemList.replaceChildren();
  problemsInput.value = "";
  afterProblemsInput.value = "";
  if (!trainingId) {
    setProblemStatus("请选择训练后加载题目");
    setAfterProblemStatus("请选择训练后加载课后题");
    generateOutput();
    return;
  }

  const password = document.querySelector("#profileForm").elements.trainingPassword.value.trim();
  setProblemStatus("题目加载中...");
  setAfterProblemStatus("课后题加载中...");
  try {
    const params = new URLSearchParams({
      trainingId,
      groupId: teamSelect.value,
      includePrevious: "1",
    });
    if (password) params.set("trainingPassword", password);
    const payload = await fetchJson(`/api/problems?${params.toString()}`);
    const currentProblems = payload.problems.filter((problem) => problem.source !== "previous");
    renderProblemCheckboxes(problemList, currentProblems, syncSelectedProblems);
    renderProblemCheckboxes(afterProblemList, payload.problems, syncSelectedAfterProblems, {
      showSource: true,
    });
    setProblemStatus(`已加载 ${currentProblems.length} 道课堂题，可多选`);
    setAfterProblemStatus(`已加载 ${payload.problems.length} 道候选课后题，可多选`);
  } catch (error) {
    setProblemStatus(error.message);
    setAfterProblemStatus(error.message);
  }
  generateOutput();
}

function renderStudentRows(students) {
  studentList.replaceChildren();
  students.forEach((student, index) => {
    const row = document.createElement("details");
    row.className = "student-row";
    row.open = false;
    row.dataset.uid = student.uid;
    row.dataset.username = student.username;
    row.dataset.nickname = student.nickname;

    const summary = document.createElement("summary");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.addEventListener("change", updateStudentStatusFromSelection);

    const title = document.createElement("span");
    title.className = "student-title";
    title.textContent = `${index + 1}. ${student.realName || student.nickname}`;

    const meta = document.createElement("span");
    meta.className = "student-meta";
    meta.textContent = `nickname: ${student.nickname}`;
    summary.append(checkbox, title, meta);

    const fields = document.createElement("div");
    fields.className = "student-fields";
    fields.append(
      readonlyField("uid", student.uid),
      readonlyField("username", student.username),
      readonlyField("nickname", student.nickname),
      editableRealNameField(student.realName || student.nickname, title),
    );
    row.append(summary, fields);
    studentList.appendChild(row);
  });
  updateStudentStatusFromSelection();
}

function readonlyField(labelText, value) {
  const label = document.createElement("label");
  label.textContent = labelText;
  const input = document.createElement("input");
  input.value = value || "";
  input.readOnly = true;
  label.appendChild(input);
  return label;
}

function editableRealNameField(value, titleElement) {
  const label = document.createElement("label");
  label.textContent = "real_name";
  const input = document.createElement("input");
  input.className = "real-name-input";
  input.value = value || "";
  input.addEventListener("input", () => {
    const row = input.closest(".student-row");
    const index = [...studentList.children].indexOf(row) + 1;
    titleElement.textContent = `${index}. ${input.value.trim() || row.dataset.nickname}`;
  });
  label.appendChild(input);
  return label;
}

function selectedStudentPayload() {
  return [...studentList.querySelectorAll(".student-row")]
    .filter((row) => row.querySelector("summary input[type='checkbox']").checked)
    .map((row) => ({
      uid: row.dataset.uid,
      username: row.dataset.username,
      nickname: row.dataset.nickname,
      realName: row.querySelector(".real-name-input").value.trim() || row.dataset.nickname,
    }));
}

function updateStudentStatusFromSelection() {
  const selectedCount = selectedStudentPayload().length;
  const total = studentList.querySelectorAll(".student-row").length;
  if (!total) return;
  setStudentStatus(`已选择 ${selectedCount}/${total} 名学生`);
}

async function saveStudentsJson() {
  const students = selectedStudentPayload();
  const filename = studentsFilenameInput.value.trim();
  if (!teamSelect.value) {
    setReportStatus("请先选择团队", "error");
    return;
  }
  if (!students.length) {
    setReportStatus("请至少选择一名学生", "error");
    return;
  }
  saveStudentsBtn.disabled = true;
  saveStudentsBtn.textContent = "保存中...";
  try {
    const result = await postJson("/api/students-json", {
      teamId: teamSelect.value,
      filename,
      students,
    });
    studentsJsonInput.value = result.path;
    setReportStatus(`已保存 ${result.count} 名学生到 ${result.path}`, "success");
  } catch (error) {
    setReportStatus(error.message, "error");
  } finally {
    saveStudentsBtn.disabled = false;
    saveStudentsBtn.textContent = "保存学生 JSON";
  }
}

function renderProblemCheckboxes(target, problems, onChange, options = {}) {
  target.replaceChildren();
  problems.forEach((problem) => {
    const label = document.createElement("label");
    label.className = "checkbox-row";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = problem.title;
    checkbox.dataset.problemId = problem.problemId;
    checkbox.addEventListener("change", onChange);
    const text = document.createElement("span");
    const source = problem.source === "previous" ? `上一训练：${problem.trainingTitle} / ` : "";
    text.textContent = options.showSource
      ? `${source}${problem.problemId} ${problem.title}`
      : `${problem.problemId} ${problem.title}`;
    label.append(checkbox, text);
    target.appendChild(label);
  });
  onChange();
}

function syncSelectedProblems() {
  const selected = [...problemList.querySelectorAll("input:checked")].map(
    (item) => item.value,
  );
  problemsInput.value = selected.join(",");
  generateOutput();
}

function syncSelectedAfterProblems() {
  const selected = [...afterProblemList.querySelectorAll("input:checked")].map(
    (item) => item.value,
  );
  afterProblemsInput.value = selected.join(",");
  generateOutput();
}

function buildProfileFeedback(data) {
  const team = clean(data.teamName || data.team, "必填：团队名称/gid/团队链接");
  const training = clean(data.trainingTitle || data.training, "必填：训练名称");
  const problems = clean(data.problems, "必填：题目名称或题号，逗号分隔");
  const afterClassProblems = String(data.afterClassProblems || "").trim();
  const trainingPassword = String(data.trainingPassword || "").trim();

  const args = ["python3", "xdf_report.py"];
  addCliArg(args, "--team", data.team);
  addCliArg(args, "--training", data.trainingTitle || data.training);
  addCliArg(args, "--problems", data.problems);
  addCliArg(args, "--after-class-problems", afterClassProblems);
  addCliArg(args, "--training-password", trainingPassword);

  const payload = {
    team: String(data.teamName || data.team || "").trim(),
    teamId: String(data.teamId || "").trim(),
    training: String(data.trainingTitle || data.training || "").trim(),
    trainingId: String(data.trainingId || "").trim(),
    problems: String(data.problems || "").trim(),
    afterClassProblems,
    trainingPassword,
    studentsJson: String(data.studentsJson || "").trim(),
  };

  const checks = [
    data.team ? "- 团队已选择" : "- 缺少团队：对应 `--team`",
    data.training ? "- 训练已选择" : "- 缺少训练：对应 `--training`",
    data.problems ? "- 课堂题目已填写" : "- 缺少课堂题目：对应 `--problems`",
    afterClassProblems
      ? "- 已填写课后题：脚本会尝试匹配当前训练和上一训练"
      : "- 未填写课后题：Excel 课后作业区域保持空白",
  ];

  return sentenceJoin([
    "# 新东方学情反馈表生成",
    `## 必填参数\n- 团队：${team}\n- 训练：${training}\n- 课堂题目：${problems}`,
    `## 可选参数\n- 课后题：${afterClassProblems || "未填写"}\n- 训练密码：${trainingPassword ? "已填写" : "未填写"}`,
    `## 复制到终端运行\n\`\`\`bash\n${args.join(" ")}\n\`\`\``,
    `## 后端接口草案\n\`\`\`json\n${JSON.stringify(payload, null, 2)}\n\`\`\``,
    `## 运行前检查\n${checks.join("\n")}`,
  ]);
}

function selectedValues(container) {
  return [...container.querySelectorAll("input:checked")].map((item) => item.value);
}

function setReportStatus(message, type = "info") {
  reportStatus.hidden = false;
  reportStatus.textContent = message;
  reportStatus.dataset.type = type;
}

function clearReportStatus() {
  reportStatus.hidden = true;
  reportStatus.textContent = "";
  delete reportStatus.dataset.type;
}

async function generateReport() {
  const payload = {
    teamId: teamSelect.value,
    trainingId: trainingSelect.value,
    trainingPassword: document.querySelector("#profileForm").elements.trainingPassword.value.trim(),
    problems: selectedValues(problemList),
    afterClassProblems: selectedValues(afterProblemList),
    studentsJson: studentsJsonInput.value,
  };
  if (!payload.teamId) {
    setReportStatus("请先选择团队", "error");
    return;
  }
  if (!payload.trainingId) {
    setReportStatus("请先选择训练", "error");
    return;
  }
  if (!payload.problems.length) {
    setReportStatus("请至少选择一道课堂题目", "error");
    return;
  }

  generateReportBtn.disabled = true;
  generateReportBtn.textContent = "生成中...";
  setReportStatus("正在生成 Excel，请稍等...", "info");
  try {
    const result = await postJson("/api/reports", payload);
    const link = document.createElement("a");
    link.href = result.downloadUrl;
    link.download = result.filename || "";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setReportStatus("Excel 已生成，浏览器正在下载。", "success");
  } catch (error) {
    setReportStatus(error.message, "error");
  } finally {
    generateReportBtn.disabled = false;
    generateReportBtn.textContent = "生成 Excel";
  }
}

function buildServiceScript(data) {
  const student = clean(data.studentName, "孩子");
  const scenario = clean(data.scenario, "课后总结");
  const level = clean(data.level, "良好");
  const facts = clean(data.facts);
  const goal = clean(data.goal, "后面继续巩固课堂重点，稳定完成同类题。");

  const opener = {
    课后总结: `${student}今天整体状态还可以，我这边简单和您反馈一下课堂情况。`,
    作业提醒: `${student}今天课堂内容已经过了一遍，课后这块建议再跟进一下作业。`,
    续课沟通: `${student}这段时间的学习情况有一些可以继续往前推进的点，我和您同步一下。`,
    问题预警: `${student}今天课堂里有几个点需要稍微关注一下，我先和您说清楚。`,
  }[scenario];

  const levelSentence = {
    优秀: "孩子理解比较快，课堂上不只是跟步骤，也能自己判断一些细节。",
    良好: "孩子大部分内容能跟上，遇到细节问题时，提醒后也能调整过来。",
    中等: "孩子能完成主要流程，但有些地方还不够稳定，需要再练几次。",
    需关注: "孩子目前不是完全不会，而是容易在关键步骤上断掉，需要课后把基础再压实。",
  }[level];

  return sentenceJoin([
    opener,
    levelSentence,
    `具体看，${facts}`,
    `后面建议：${goal}`,
  ]);
}

function buildLessonPrep(data) {
  const topic = clean(data.lessonTopic, "课程主题");
  const audience = clean(data.audience, "授课对象");
  const lessonType = clean(data.lessonType, "新授课");
  const duration = clean(data.duration, "待定");
  const studentProfile = clean(data.studentProfile);
  const keyPoints = clean(data.keyPoints);
  const materials = clean(data.materials);

  return sentenceJoin([
    `# ${topic}课前备课`,
    `## 基本信息\n- 对象：${audience}\n- 课型：${lessonType}\n- 时长：${duration}`,
    `## 学情分析\n${studentProfile}`,
    `## 重点与难点\n${keyPoints}`,
    `## 课堂流程建议\n1. 导入：用一个学生熟悉的问题引出本节主题。\n2. 建模：把概念、规则或题型拆成可观察的步骤。\n3. 例题：先做标准题，再做一个容易出错的变式。\n4. 练习：安排分层练习，及时记录错因。\n5. 总结：让学生说出本节课最关键的一句话或一个步骤。`,
    `## 题目与材料\n${materials}`,
    `## 课后跟进\n根据课堂错题整理 2-3 个主要薄弱点，生成对应巩固题和家长反馈。`,
  ]);
}

function generateOutput() {
  const meta = toolMeta[currentTool];
  const data = getFormData(meta.formId);
  latestOutput = meta.build(data);
}

function switchTool(tool) {
  currentTool = tool;
  toolTitle.textContent = toolMeta[tool].title;
  navButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tool === tool);
  });
  toolViews.forEach((view) => {
    view.classList.toggle("active", view.dataset.toolView === tool);
  });
  restoreDraft();
  generateOutput();
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  window.setTimeout(() => toast.remove(), 1800);
}

function draftKey() {
  return `teaching-toolbox:${currentTool}`;
}

function saveDraft() {
  const meta = toolMeta[currentTool];
  const data = getFormData(meta.formId);
  localStorage.setItem(draftKey(), JSON.stringify(data));
  showToast("草稿已保存");
}

function restoreDraft() {
  const meta = toolMeta[currentTool];
  const form = document.querySelector(`#${meta.formId}`);
  const raw = localStorage.getItem(draftKey());
  if (!raw) return;
  const data = JSON.parse(raw);
  Object.entries(data).forEach(([key, value]) => {
    const field = form.elements[key];
    if (field) field.value = value;
  });
}

navButtons.forEach((button) => {
  button.addEventListener("click", () => switchTool(button.dataset.tool));
});

document.querySelectorAll("form").forEach((form) => {
  form.addEventListener("input", generateOutput);
  form.addEventListener("change", generateOutput);
});

document.querySelector("#saveDraftBtn")?.addEventListener("click", saveDraft);
generateReportBtn.addEventListener("click", generateReport);
document.querySelector("#selectAllProblemsBtn").addEventListener("click", () => {
  problemList.querySelectorAll("input[type='checkbox']").forEach((item) => {
    item.checked = true;
  });
  syncSelectedProblems();
});
document.querySelector("#clearProblemsBtn").addEventListener("click", () => {
  problemList.querySelectorAll("input[type='checkbox']").forEach((item) => {
    item.checked = false;
  });
  syncSelectedProblems();
});
document.querySelector("#selectAllAfterProblemsBtn").addEventListener("click", () => {
  afterProblemList.querySelectorAll("input[type='checkbox']").forEach((item) => {
    item.checked = true;
  });
  syncSelectedAfterProblems();
});
document.querySelector("#clearAfterProblemsBtn").addEventListener("click", () => {
  afterProblemList.querySelectorAll("input[type='checkbox']").forEach((item) => {
    item.checked = false;
  });
  syncSelectedAfterProblems();
});
document.querySelector("#selectAllStudentsBtn").addEventListener("click", () => {
  studentList.querySelectorAll("summary input[type='checkbox']").forEach((item) => {
    item.checked = true;
  });
  updateStudentStatusFromSelection();
});
document.querySelector("#clearStudentsBtn").addEventListener("click", () => {
  studentList.querySelectorAll("summary input[type='checkbox']").forEach((item) => {
    item.checked = false;
  });
  updateStudentStatusFromSelection();
});
saveStudentsBtn.addEventListener("click", saveStudentsJson);
teamSelect.addEventListener("change", () => {
  const selected = teamSelect.selectedOptions[0];
  teamIdInput.value = teamSelect.value;
  teamNameInput.value = selected && teamSelect.value ? selected.textContent.replace(/（gid=.*$/, "") : "";
  studentsFilenameInput.value = teamSelect.value ? `students.${teamSelect.value}.json` : "students.json";
  studentsJsonInput.value = "";
  trainingTitleInput.value = "";
  trainingIdInput.value = "";
  loadStudents(teamSelect.value);
  loadTrainings(teamSelect.value);
});
trainingSelect.addEventListener("change", () => {
  const selected = trainingSelect.selectedOptions[0];
  trainingIdInput.value = trainingSelect.value;
  trainingTitleInput.value = selected && trainingSelect.value ? selected.textContent : "";
  loadProblems(trainingSelect.value);
});
document.querySelector("#profileForm").elements.trainingPassword.addEventListener("change", () => {
  if (trainingSelect.value) loadProblems(trainingSelect.value);
});

restoreDraft();
loadTeams();
generateOutput();
