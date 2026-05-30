const toolMeta = {
  profile: {
    title: "学情反馈表",
    formId: "profileForm",
    build: buildProfileFeedback,
  },
  problemBank: {
    title: "题库检索",
    formId: "problemBankForm",
    build: buildProblemBankPreview,
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
  agentStudio: {
    title: "Agent 工作台",
    formId: "agentStudioForm",
    build: buildAgentStudioPreview,
  },
};

let currentTool = "profile";
let latestOutput = "";
let studentCandidates = [];

const toolTitle = document.querySelector("#toolTitle");
const loginScreen = document.querySelector("#loginScreen");
const appShell = document.querySelector("#appShell");
const loginForm = document.querySelector("#loginForm");
const loginBtn = document.querySelector("#loginBtn");
const loginStatus = document.querySelector("#loginStatus");
const logoutBtn = document.querySelector("#logoutBtn");
const currentUser = document.querySelector("#currentUser");
const userMenu = document.querySelector("#userMenu");
const userMenuBtn = document.querySelector("#userMenuBtn");
const userMenuList = document.querySelector("#userMenuList");
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
const studentsJsonUploadInput = document.querySelector("#studentsJsonUploadInput");
const uploadStudentsJsonBtn = document.querySelector("#uploadStudentsJsonBtn");
const saveStudentsBtn = document.querySelector("#saveStudentsBtn");
const savedStudentsStatus = document.querySelector("#savedStudentsStatus");
const retryStudentsBtn = document.querySelector("#retryStudentsBtn");
const retryProblemsBtn = document.querySelector("#retryProblemsBtn");
const retryAfterProblemsBtn = document.querySelector("#retryAfterProblemsBtn");
const teamNameInput = document.querySelector("#teamNameInput");
const teamIdInput = document.querySelector("#teamIdInput");
const trainingTitleInput = document.querySelector("#trainingTitleInput");
const trainingIdInput = document.querySelector("#trainingIdInput");
const reportStatus = document.querySelector("#reportStatus");
const generateReportBtn = document.querySelector("#generateReportBtn");
const problemBankStatus = document.querySelector("#problemBankStatus");
const problemBankResults = document.querySelector("#problemBankResults");
const searchProblemBankBtn = document.querySelector("#searchProblemBankBtn");
const agentStudioStatus = document.querySelector("#agentStudioStatus");
const agentToolRegistry = document.querySelector("#agentToolRegistry");
const agentRunList = document.querySelector("#agentRunList");
const createAgentRunBtn = document.querySelector("#createAgentRunBtn");

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

async function fetchJson(url) {
  let response;
  try {
    response = await fetch(url);
  } catch (error) {
    throw new Error(friendlyNetworkMessage(error));
  }
  const payload = await readJsonResponse(response);
  if (!response.ok) {
    throw apiError(payload.error, response.status);
  }
  return payload;
}

async function postJson(url, body) {
  let response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (error) {
    throw new Error(friendlyNetworkMessage(error));
  }
  const payload = await readJsonResponse(response);
  if (!response.ok) {
    throw apiError(payload.error, response.status);
  }
  return payload;
}

async function readJsonResponse(response) {
  const text = await response.text();
  try {
    return text ? JSON.parse(text) : {};
  } catch (_error) {
    const preview = text.trim().slice(0, 80) || "空响应";
    if (preview.startsWith("<!DOCTYPE") || preview.startsWith("<html")) {
      throw new Error("页面没有连到工具箱服务。请确认已经启动服务，并从 http://127.0.0.1:8765 打开。");
    }
    throw new Error("服务返回了异常内容，请刷新页面后重试。");
  }
}

function friendlyNetworkMessage(_error) {
  return "暂时连接不上工具箱服务。请确认服务已启动，然后刷新页面重试。";
}

function friendlyApiMessage(message, status) {
  const text = String(message || "").trim();
  if (text) return text;
  if (status === 401) return "登录状态已失效，请重新登录。";
  if (status === 404) return "没有找到对应内容，请刷新页面后重试。";
  return "操作没有完成，请稍后重试。";
}

function apiError(message, status) {
  const error = new Error(friendlyApiMessage(message, status));
  error.status = status;
  return error;
}

function displayError(error, fallback = "操作没有完成，请稍后重试。") {
  return friendlyApiMessage(error && error.message, 0) || fallback;
}

function handleSessionError(error) {
  if (error && error.status === 401) {
    resetAppData();
    showLogin();
    setLoginStatus("登录状态已失效，请重新登录。", "error");
    return true;
  }
  return false;
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
  if (!problemStatus) return;
  problemStatus.textContent = message;
}

function setAfterProblemStatus(message) {
  if (!afterProblemStatus) return;
  afterProblemStatus.textContent = message;
}

function setStudentStatus(message) {
  if (!studentStatus) return;
  studentStatus.textContent = message;
}

function setSavedStudentsStatus(message) {
  if (!savedStudentsStatus) return;
  savedStudentsStatus.textContent = message;
}

function markStudentsDirty() {
  studentsJsonInput.value = "";
  setSavedStudentsStatus("名单有修改，请保存后再生成 Excel。");
}

function setRetryButton(button, visible) {
  button.hidden = !visible;
}

function setLoginStatus(message, type = "info") {
  loginStatus.hidden = false;
  loginStatus.textContent = message;
  loginStatus.dataset.type = type;
}

function clearLoginStatus() {
  loginStatus.hidden = true;
  loginStatus.textContent = "";
  delete loginStatus.dataset.type;
}

function showLogin() {
  document.body.dataset.authState = "logged-out";
  loginScreen.hidden = false;
  appShell.hidden = true;
  closeUserMenu();
}

function showApp(account) {
  document.body.dataset.authState = "logged-in";
  loginScreen.hidden = true;
  appShell.hidden = false;
  currentUser.textContent = account || "当前用户";
}

function closeUserMenu() {
  userMenuList.hidden = true;
  userMenuBtn.setAttribute("aria-expanded", "false");
}

function toggleUserMenu() {
  const willOpen = userMenuList.hidden;
  userMenuList.hidden = !willOpen;
  userMenuBtn.setAttribute("aria-expanded", String(willOpen));
}

function resetAppData() {
  studentCandidates = [];
  setSelectOptions(teamSelect, [], "请选择团队");
  setSelectOptions(trainingSelect, [], "请先选择团队");
  trainingSelect.disabled = true;
  studentList.replaceChildren();
  problemList.replaceChildren();
  afterProblemList.replaceChildren();
  studentsJsonInput.value = "";
  problemsInput.value = "";
  afterProblemsInput.value = "";
  setStudentStatus("请选择团队后加载学生");
  setSavedStudentsStatus("保存后，下次选择该团队会自动使用这份名单");
  setProblemStatus("请选择训练后加载题目");
  setAfterProblemStatus("请选择训练后加载课后题");
  setProblemBankStatus("登录后可检索 OJ/GESP 题库");
  setAgentStudioStatus("先创建可追踪 run，后续再接真实执行");
  problemBankResults.replaceChildren();
  agentToolRegistry.replaceChildren();
  agentRunList.replaceChildren();
  clearReportStatus();
}

async function checkLogin() {
  try {
    const payload = await fetchJson("/api/me");
    if (payload.loggedIn) {
      showApp(payload.account);
      await loadTeams();
    } else {
      showLogin();
    }
  } catch (error) {
    showLogin();
    setLoginStatus(displayError(error), "error");
  }
}

async function login(event) {
  event.preventDefault();
  clearLoginStatus();
  const data = Object.fromEntries(new FormData(loginForm).entries());
  const account = String(data.account || "").trim();
  const password = String(data.password || "").trim();
  if (!/^1\d{10}$/.test(account)) {
    setLoginStatus("请输入 11 位 OJ 手机号。", "error");
    return;
  }
  if (!password) {
    setLoginStatus("请输入 OJ 密码。", "error");
    return;
  }
  loginBtn.disabled = true;
  loginBtn.textContent = "登录中...";
  try {
    const payload = await postJson("/api/login", {
      account,
      password,
      remember: data.remember === "on",
    });
    resetAppData();
    showApp(payload.account);
    await loadTeams();
  } catch (error) {
    setLoginStatus(displayError(error, "登录失败，请检查手机号和密码后重试。"), "error");
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = "登录";
  }
}

async function logout() {
  try {
    await postJson("/api/logout", {});
  } finally {
    resetAppData();
    showLogin();
  }
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
    if (handleSessionError(error)) return;
    setSelectOptions(teamSelect, [], "团队加载失败");
    setProblemStatus(displayError(error, "团队加载失败，请稍后重试。"));
  }
}

function setProblemBankStatus(message) {
  if (!problemBankStatus) return;
  problemBankStatus.textContent = message;
}

function setAgentStudioStatus(message) {
  if (!agentStudioStatus) return;
  agentStudioStatus.textContent = message;
}

async function loadTrainings(groupId) {
  setRetryButton(retryProblemsBtn, false);
  setRetryButton(retryAfterProblemsBtn, false);
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
    if (handleSessionError(error)) return;
    setSelectOptions(trainingSelect, [], "训练加载失败");
    const message = displayError(error, "训练加载失败，请重新选择团队后重试。");
    setProblemStatus(message);
    setAfterProblemStatus(message);
    setRetryButton(retryProblemsBtn, true);
    setRetryButton(retryAfterProblemsBtn, true);
  }
  generateOutput();
}

async function loadStudents(groupId) {
  setRetryButton(retryStudentsBtn, false);
  studentCandidates = [];
  studentList.replaceChildren();
  studentsJsonInput.value = "";
  if (!groupId) {
    setStudentStatus("请选择团队后加载学生");
    setSavedStudentsStatus("保存后，下次选择该团队会自动使用这份名单");
    return;
  }

  setStudentStatus("学生加载中...");
  try {
    const saved = await fetchJson(`/api/saved-students?groupId=${encodeURIComponent(groupId)}`);
    if (saved.exists && saved.students.length) {
      studentCandidates = normalizeStudents(saved.students || []);
      renderStudentRows(saved.students || []);
      studentsJsonInput.value = saved.path;
      setStudentStatus(`已使用保存的学生名单，共 ${saved.count} 名学生`);
      try {
        const payload = await fetchJson(`/api/students?groupId=${encodeURIComponent(groupId)}`);
        studentCandidates = normalizeStudents(payload.students || []);
        setSavedStudentsStatus("当前正在使用已保存名单；清空后会展示 OJ 全部候选学生。");
      } catch (_error) {
        setSavedStudentsStatus("当前正在使用已保存名单；OJ 候选名单暂时不可用。");
      }
      return;
    }
    const payload = await fetchJson(`/api/students?groupId=${encodeURIComponent(groupId)}`);
    studentCandidates = normalizeStudents(payload.students || []);
    renderStudentRows(payload.students || []);
    setStudentStatus(`已从 OJ 加载 ${payload.students.length} 名学生，请确认后保存名单`);
    setSavedStudentsStatus("还没有保存名单。保存后，下次选择该团队会自动使用。");
  } catch (error) {
    if (handleSessionError(error)) return;
    setStudentStatus(displayError(error, "学生名单加载失败，请稍后重试。"));
    setSavedStudentsStatus("学生名单暂时不可用，请重新加载。");
    setRetryButton(retryStudentsBtn, true);
  }
}

async function loadProblems(trainingId) {
  setRetryButton(retryProblemsBtn, false);
  setRetryButton(retryAfterProblemsBtn, false);
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
    const afterProblems = payload.problems.filter((problem) => problem.source === "previous");
    renderProblemCheckboxes(problemList, currentProblems, syncSelectedProblems);
    renderProblemCheckboxes(afterProblemList, afterProblems, syncSelectedAfterProblems, {
      showSource: true,
    });
    setProblemStatus(`已加载 ${currentProblems.length} 道课堂题，可多选`);
    setAfterProblemStatus(
      afterProblems.length
        ? `已加载上一作业列表 ${afterProblems.length} 道课后题，可多选`
        : "没有找到上一作业列表的课后题",
    );
  } catch (error) {
    if (handleSessionError(error)) return;
    const message = displayError(error, "题目加载失败，请检查训练密码后重试。");
    setProblemStatus(message);
    setAfterProblemStatus(message);
    setRetryButton(retryProblemsBtn, true);
    setRetryButton(retryAfterProblemsBtn, true);
  }
  generateOutput();
}

function normalizeStudent(student) {
  return {
    uid: String(student.uid ?? student.id ?? "").trim(),
    username: String(student.username ?? student.userName ?? student.user_name ?? "").trim(),
    nickname: String(student.nickname ?? student.nickName ?? student.nick_name ?? student.name ?? "").trim(),
    realName: String(student.realName ?? student.real_name ?? student.nickname ?? student.name ?? "").trim(),
    school: String(student.school ?? student.academy ?? "").trim(),
    phone: String(student.phone ?? student.mobile ?? "").trim(),
  };
}

function normalizeStudents(students) {
  return (students || [])
    .map(normalizeStudent)
    .filter((student) => student.uid && student.username && student.nickname);
}

function extractStudentsFromJson(payload) {
  if (Array.isArray(payload)) return normalizeStudents(payload);
  if (payload && Array.isArray(payload.students)) return normalizeStudents(payload.students);
  return [];
}

function renderStudentRows(students, options = {}) {
  const checkedByDefault = options.checkedByDefault !== false;
  studentList.replaceChildren();
  const header = document.createElement("div");
  header.className = "student-header";
  header.innerHTML = "<span></span><span>real_name</span><span>nickname</span><span>user_name</span><span>school</span><span>phone</span>";
  studentList.appendChild(header);
  normalizeStudents(students).forEach((student, index) => {
    const row = document.createElement("div");
    row.className = "student-row";
    row.dataset.uid = student.uid;
    row.dataset.username = student.username;
    row.dataset.nickname = student.nickname;
    row.dataset.school = student.school;
    row.dataset.phone = student.phone;

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = checkedByDefault;
    checkbox.addEventListener("change", () => {
      updateStudentStatusFromSelection();
      markStudentsDirty();
    });

    const realNameInput = document.createElement("input");
    realNameInput.className = "real-name-input";
    realNameInput.value = student.realName || student.nickname || "";
    realNameInput.setAttribute("aria-label", `第 ${index + 1} 位学生 real_name`);
    realNameInput.addEventListener("input", markStudentsDirty);

    const nickname = document.createElement("span");
    nickname.className = "student-cell";
    nickname.textContent = student.nickname || "";

    const username = document.createElement("span");
    username.className = "student-cell";
    username.textContent = student.username || "";

    const school = document.createElement("span");
    school.className = "student-cell";
    school.textContent = student.school || "";

    const phone = document.createElement("span");
    phone.className = "student-cell";
    phone.textContent = student.phone || "";

    row.append(checkbox, realNameInput, nickname, username, school, phone);
    studentList.appendChild(row);
  });
  updateStudentStatusFromSelection();
}

function showAllStudentCandidatesUnchecked() {
  if (!studentCandidates.length) {
    studentList.replaceChildren();
    studentsJsonInput.value = "";
    setStudentStatus("没有可展示的候选学生，请先选择团队或上传 JSON");
    setSavedStudentsStatus("当前没有候选名单。");
    return;
  }
  renderStudentRows(studentCandidates, { checkedByDefault: false });
  studentsJsonInput.value = "";
  setStudentStatus(`已清空选择，展示全部 ${studentCandidates.length} 名候选学生`);
  setSavedStudentsStatus("请重新勾选需要生成学情反馈表的学生。");
}

async function importStudentsJsonFile(file) {
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const students = extractStudentsFromJson(payload);
    if (!students.length) {
      throw new Error("JSON 中没有识别到学生名单。");
    }
    studentCandidates = students;
    renderStudentRows(students);
    studentsJsonInput.value = "";
    if (teamSelect.value) {
      studentsFilenameInput.value = `students.${teamSelect.value}.json`;
    }
    setStudentStatus(`已从 JSON 生成 ${students.length} 名学生`);
    setSavedStudentsStatus("上传内容尚未保存；确认名单后请点击保存学生名单。");
    setReportStatus(`已导入 ${students.length} 名学生，请确认后保存。`, "success");
  } catch (error) {
    setReportStatus(displayError(error, "JSON 学生名单导入失败，请检查文件格式。"), "error");
  } finally {
    studentsJsonUploadInput.value = "";
  }
}

function selectedStudentPayload() {
  return [...studentList.querySelectorAll(".student-row")]
    .filter((row) => row.querySelector("input[type='checkbox']").checked)
    .map((row) => ({
      uid: row.dataset.uid,
      username: row.dataset.username,
      nickname: row.dataset.nickname,
      realName: row.querySelector(".real-name-input").value.trim() || row.dataset.nickname,
      school: row.dataset.school || "",
      phone: row.dataset.phone || "",
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
    setStudentStatus(`已保存 ${result.count} 名学生，下次会自动使用`);
    setSavedStudentsStatus("已保存当前名单；后续生成 Excel 会使用这份名单。");
    setReportStatus(`已保存 ${result.count} 名学生。`, "success");
  } catch (error) {
    if (handleSessionError(error)) return;
    setReportStatus(displayError(error, "学生名单保存失败，请稍后重试。"), "error");
  } finally {
    saveStudentsBtn.disabled = false;
    saveStudentsBtn.textContent = "保存学生名单";
  }
}

async function ensureStudentsSavedForReport() {
  if (studentsJsonInput.value) return true;
  const students = selectedStudentPayload();
  if (!students.length) {
    setReportStatus("请至少选择一名学生", "error");
    focusField("students");
    return false;
  }
  saveStudentsBtn.disabled = true;
  saveStudentsBtn.textContent = "保存中...";
  try {
    const result = await postJson("/api/students-json", {
      teamId: teamSelect.value,
      filename: studentsFilenameInput.value.trim(),
      students,
    });
    studentsJsonInput.value = result.path;
    setStudentStatus(`已保存 ${result.count} 名学生，下次会自动使用`);
    setSavedStudentsStatus("已保存当前名单；后续生成 Excel 会使用这份名单。");
    return true;
  } catch (error) {
    if (handleSessionError(error)) return false;
    setReportStatus(displayError(error, "学生名单保存失败，请稍后重试。"), "error");
    focusField("students");
    return false;
  } finally {
    saveStudentsBtn.disabled = false;
    saveStudentsBtn.textContent = "保存学生名单";
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

  const checks = [
    data.team ? "- 团队已选择" : "- 请先选择团队",
    data.training ? "- 训练已选择" : "- 请先选择训练",
    data.problems ? "- 课堂题目已选择" : "- 请至少选择一道课堂题目",
    afterClassProblems
      ? "- 已选择课后题"
      : "- 未填写课后题：Excel 课后作业区域保持空白",
  ];

  return sentenceJoin([
    "# 学情反馈表",
    `## 当前选择\n- 团队：${team}\n- 训练：${training}\n- 课堂题目：${problems}`,
    `## 可选内容\n- 课后题：${afterClassProblems || "未填写"}\n- 训练密码：${trainingPassword ? "已填写" : "未填写"}`,
    `## 检查\n${checks.join("\n")}`,
  ]);
}

function buildProblemBankPreview(data) {
  const query = clean(data.query, "题号或关键词");
  const limit = clean(data.limit, "8");
  const detail = data.includeDetail === "on" ? "拉取题面详情" : "只看搜索结果";
  return sentenceJoin([
    "# 题库检索",
    `- 查询：${query}`,
    `- 数量：${limit}`,
    `- 模式：${detail}`,
  ]);
}

function selectedValues(container) {
  return [...container.querySelectorAll("input:checked")].map((item) => item.value);
}

function toggleAllCheckboxes(container, onChange) {
  const checkboxes = [...container.querySelectorAll("input[type='checkbox']")];
  const shouldCheck = checkboxes.some((item) => !item.checked);
  checkboxes.forEach((item) => {
    item.checked = shouldCheck;
  });
  onChange();
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

function focusField(fieldName) {
  const field = document.querySelector(`[data-field="${fieldName}"]`);
  if (!field) return;
  field.scrollIntoView({ behavior: "smooth", block: "center" });
  field.classList.add("field-attention");
  window.setTimeout(() => field.classList.remove("field-attention"), 1400);
  const control = field.querySelector("select, input, textarea, button");
  if (control) {
    window.setTimeout(() => control.focus({ preventScroll: true }), 250);
  }
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
    focusField("team");
    return;
  }
  if (!payload.trainingId) {
    setReportStatus("请先选择训练", "error");
    focusField("training");
    return;
  }
  if (!payload.problems.length) {
    setReportStatus("请至少选择一道课堂题目", "error");
    focusField("problems");
    return;
  }
  if (!(await ensureStudentsSavedForReport())) {
    return;
  }
  payload.studentsJson = studentsJsonInput.value;

  generateReportBtn.disabled = true;
  generateReportBtn.textContent = "生成中...";
  setReportStatus("正在读取成绩并生成 Excel，可能需要 10-30 秒，请稍等。", "info");
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
    if (handleSessionError(error)) return;
    setReportStatus(displayError(error, "Excel 生成失败，请检查选择内容后重试。"), "error");
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

function buildAgentStudioPreview(data) {
  const title = clean(data.title, "任务名称");
  const goal = clean(data.goal, "任务目标");
  const evidence = clean(data.evidenceQueries, "证据关键词");
  const auditLevel = clean(data.auditLevel, "strict");
  const outputs = collectCheckedValues("#agentStudioForm", "outputs").join("、") || "待选择";
  return sentenceJoin([
    `# ${title}`,
    `## 目标\n${goal}`,
    `## 证据检索\n${evidence}`,
    `## 输出\n${outputs}`,
    `## 审计等级\n${auditLevel}`,
  ]);
}

function collectCheckedValues(formSelector, name) {
  return [
    ...document.querySelectorAll(`${formSelector} input[name="${name}"]:checked`),
  ].map((item) => item.value);
}

function generateOutput() {
  const meta = toolMeta[currentTool];
  const data = getFormData(meta.formId);
  latestOutput = meta.build(data);
}

function lineList(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function renderProblemBankResults(items) {
  problemBankResults.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "没有找到题目。";
    problemBankResults.appendChild(empty);
    return;
  }
  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = "result-card";
    const meta = [
      item.tags && item.tags.length ? `标签：${item.tags.join("、")}` : "标签：无",
      item.total != null && item.ac != null ? `提交/通过：${item.total}/${item.ac}` : "",
    ]
      .filter(Boolean)
      .join(" · ");
    article.innerHTML = `
      <h3>${item.problemId} ${item.title}</h3>
      <p>${meta}</p>
      <pre></pre>
    `;
    article.querySelector("pre").textContent = item.markdown || "";
    problemBankResults.appendChild(article);
  });
}

async function searchProblemBank() {
  const data = getFormData("problemBankForm");
  const query = String(data.query || "").trim();
  if (!query) {
    setProblemBankStatus("请输入题号或关键词。");
    return;
  }
  searchProblemBankBtn.disabled = true;
  searchProblemBankBtn.textContent = "检索中...";
  setProblemBankStatus("正在检索 OJ/GESP 题库...");
  try {
    const params = new URLSearchParams({
      query,
      limit: String(data.limit || 8),
      includeDetail: data.includeDetail === "on" ? "1" : "0",
    });
    const payload = await fetchJson(`/api/problem-bank/search?${params.toString()}`);
    renderProblemBankResults(payload.items || []);
    setProblemBankStatus(`找到 ${payload.count} 条结果。`);
  } catch (error) {
    if (handleSessionError(error)) return;
    setProblemBankStatus(displayError(error, "题库检索失败，请稍后重试。"));
  } finally {
    searchProblemBankBtn.disabled = false;
    searchProblemBankBtn.textContent = "检索题库";
  }
}

function renderToolRegistry(tools) {
  agentToolRegistry.replaceChildren();
  tools.forEach((tool) => {
    const card = document.createElement("article");
    card.className = "tool-card";
    card.innerHTML = `
      <div>
        <h4>${tool.name}</h4>
        <p>${tool.description}</p>
      </div>
      <span data-status="${tool.status}">${tool.status}</span>
    `;
    agentToolRegistry.appendChild(card);
  });
}

function renderAgentRuns(runs) {
  agentRunList.replaceChildren();
  if (!runs.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "还没有运行记录。";
    agentRunList.appendChild(empty);
    return;
  }
  runs.forEach((run) => {
    const article = document.createElement("article");
    article.className = "result-card compact";
    article.innerHTML = `
      <h3>${run.title}</h3>
      <p>run_id: <code>${run.runId}</code> · ${run.status} · ${run.createdAt}</p>
      <p>${run.goal}</p>
    `;
    agentRunList.appendChild(article);
  });
}

async function loadAgentStudio() {
  try {
    const [tools, runs] = await Promise.all([
      fetchJson("/api/agent/tools"),
      fetchJson("/api/agent/runs"),
    ]);
    renderToolRegistry(tools.tools || []);
    renderAgentRuns(runs.runs || []);
  } catch (error) {
    if (handleSessionError(error)) return;
    setAgentStudioStatus(displayError(error, "Agent 工作台加载失败，请稍后重试。"));
  }
}

async function createAgentRun() {
  const data = getFormData("agentStudioForm");
  const payload = {
    title: data.title,
    goal: data.goal,
    auditLevel: data.auditLevel,
    evidenceQueries: lineList(data.evidenceQueries),
    outputs: collectCheckedValues("#agentStudioForm", "outputs"),
  };
  createAgentRunBtn.disabled = true;
  createAgentRunBtn.textContent = "创建中...";
  try {
    const run = await postJson("/api/agent/runs", payload);
    setAgentStudioStatus(`已创建 run：${run.runId}`);
    await loadAgentStudio();
  } catch (error) {
    if (handleSessionError(error)) return;
    setAgentStudioStatus(displayError(error, "创建 Agent run 失败，请检查输入。"));
  } finally {
    createAgentRunBtn.disabled = false;
    createAgentRunBtn.textContent = "创建 Run";
  }
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
  if (tool === "agentStudio") {
    loadAgentStudio();
  }
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

loginForm.addEventListener("submit", login);
userMenuBtn.addEventListener("click", toggleUserMenu);
logoutBtn.addEventListener("click", logout);
document.addEventListener("click", (event) => {
  if (!userMenu.contains(event.target)) closeUserMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeUserMenu();
});
document.querySelector("#saveDraftBtn")?.addEventListener("click", saveDraft);
generateReportBtn.addEventListener("click", generateReport);
searchProblemBankBtn.addEventListener("click", searchProblemBank);
createAgentRunBtn.addEventListener("click", createAgentRun);
document.querySelector("#selectAllProblemsBtn").addEventListener("click", () => {
  toggleAllCheckboxes(problemList, syncSelectedProblems);
});
document.querySelector("#clearProblemsBtn").addEventListener("click", () => {
  problemList.querySelectorAll("input[type='checkbox']").forEach((item) => {
    item.checked = false;
  });
  syncSelectedProblems();
});
document.querySelector("#selectAllAfterProblemsBtn").addEventListener("click", () => {
  toggleAllCheckboxes(afterProblemList, syncSelectedAfterProblems);
});
document.querySelector("#clearAfterProblemsBtn").addEventListener("click", () => {
  afterProblemList.querySelectorAll("input[type='checkbox']").forEach((item) => {
    item.checked = false;
  });
  syncSelectedAfterProblems();
});
document.querySelector("#selectAllStudentsBtn").addEventListener("click", () => {
  toggleAllCheckboxes(studentList, updateStudentStatusFromSelection);
  markStudentsDirty();
});
document.querySelector("#clearStudentsBtn").addEventListener("click", () => {
  showAllStudentCandidatesUnchecked();
});
uploadStudentsJsonBtn.addEventListener("click", () => studentsJsonUploadInput.click());
studentsJsonUploadInput.addEventListener("change", () => {
  importStudentsJsonFile(studentsJsonUploadInput.files[0]);
});
saveStudentsBtn.addEventListener("click", saveStudentsJson);
retryStudentsBtn.addEventListener("click", () => loadStudents(teamSelect.value));
retryProblemsBtn.addEventListener("click", () => loadProblems(trainingSelect.value));
retryAfterProblemsBtn.addEventListener("click", () => loadProblems(trainingSelect.value));
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

showLogin();
document.body.dataset.authState = "checking";
checkLogin();
generateOutput();
