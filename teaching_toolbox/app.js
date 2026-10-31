const toolMeta = {
  profile: {
    title: "学情反馈表",
    formId: "profileForm",
    build: buildProfileFeedback,
    needsOj: true,
  },
  feedback: {
    title: "课后反馈",
    formId: "feedbackForm",
    build: buildFeedbackPreview,
  },
};

let currentTool = "feedback";
let latestOutput = "";
let studentCandidates = [];
let feedbackStudents = [];
let pendingFeedbackScreenshot = null;
let isLoggedIn = false;
let currentReport = null;
let reportEdits = {};
const feedbackStudentsState = "teaching-toolbox:feedbackStudentsState";
const sidebarWidthState = "teaching-toolbox:sidebarWidth";
const themeState = "teaching-toolbox:theme";
const FEEDBACK_DIMENSIONS = [
  {
    key: "understanding",
    label: "理解程度",
    options: ["理解清楚", "初步理解", "还需熟悉"],
  },
  {
    key: "independence",
    label: "独立完成代码",
    options: ["基本独立", "提示后完成", "分步引导"],
  },
  {
    key: "classroomState",
    label: "上课状态",
    options: ["积极回答问题", "很投入", "比较稳定", "需要提醒"],
  },
  {
    key: "mainIssue",
    label: "存在问题",
    options: ["概念理解", "审题", "边界条件", "代码实现", "调试"],
  },
];

const toolTitle = document.querySelector("#toolTitle");
const loginScreen = document.querySelector("#loginScreen");
const appShell = document.querySelector("#appShell");
const sidebarResizeHandle = document.querySelector("#sidebarResizeHandle");
const loginForm = document.querySelector("#loginForm");
const loginBtn = document.querySelector("#loginBtn");
const loginStatus = document.querySelector("#loginStatus");
const openLoginBtn = document.querySelector("#openLoginBtn");
const cancelLoginBtn = document.querySelector("#cancelLoginBtn");
const logoutBtn = document.querySelector("#logoutBtn");
const currentUser = document.querySelector("#currentUser");
const userMenu = document.querySelector("#userMenu");
const userMenuBtn = document.querySelector("#userMenuBtn");
const userMenuList = document.querySelector("#userMenuList");
const navButtons = document.querySelectorAll(".nav-button");
const toolViews = document.querySelectorAll("[data-tool-view]");
const teamSelect = document.querySelector("#teamSelect");
const trainingSelect = document.querySelector("#trainingSelect");
const reportTypeSelect = document.querySelector("#reportTypeSelect");
const classProblemField = document.querySelector("#classProblemField");
const afterProblemField = document.querySelector("#afterProblemField");
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
const reportResult = document.querySelector("#reportResult");
const reportResultTitle = document.querySelector("#reportResultTitle");
const reportTable = document.querySelector("#reportTable");
const adjustReportBtn = document.querySelector("#adjustReportBtn");
const exitReportBtn = document.querySelector("#exitReportBtn");
const copyReportBtn = document.querySelector("#copyReportBtn");
const downloadReportBtn = document.querySelector("#downloadReportBtn");
const themeToggleBtn = document.querySelector("#themeToggleBtn");
const themeToggleText = document.querySelector("#themeToggleText");
const saveState = document.querySelector("#saveState");
const feedbackStatus = document.querySelector("#feedbackStatus");
const feedbackList = document.querySelector("#feedbackList");
const feedbackJsonUploadInput = document.querySelector("#feedbackJsonUploadInput");
const uploadFeedbackJsonBtn = document.querySelector("#uploadFeedbackJsonBtn");
const feedbackOcrStatus = document.querySelector("#feedbackOcrStatus");
const feedbackScreenshotInput = document.querySelector("#feedbackScreenshotInput");
const uploadFeedbackScreenshotBtn = document.querySelector("#uploadFeedbackScreenshotBtn");
const confirmFeedbackScreenshotBtn = document.querySelector("#confirmFeedbackScreenshotBtn");
const compressKnowledgeBtn = document.querySelector("#compressKnowledgeBtn");
const feedbackAgentSummary = document.querySelector("#feedbackAgentSummary");
const feedbackScreenshotPreview = document.querySelector("#feedbackScreenshotPreview");
const feedbackScreenshotImage = document.querySelector("#feedbackScreenshotImage");
const removeFeedbackScreenshotBtn = document.querySelector("#removeFeedbackScreenshotBtn");

const SIDEBAR_WIDTH_MIN = 240;
const SIDEBAR_WIDTH_MAX = 460;
const REPORT_SUCCESS_HIDE_MS = 3000;
let sidebarResizeSession = null;
let reportStatusHideTimer = null;

function applyTheme(theme) {
  const nextTheme = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = nextTheme;
  themeToggleBtn?.setAttribute("aria-pressed", String(nextTheme === "dark"));
  themeToggleBtn?.setAttribute("aria-label", nextTheme === "dark" ? "切换到浅色模式" : "切换到深色模式");
  if (themeToggleText) themeToggleText.textContent = nextTheme === "dark" ? "浅色" : "深色";
}

function restoreTheme() {
  const savedTheme = localStorage.getItem(themeState);
  const systemDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  applyTheme(savedTheme || (systemDark ? "dark" : "light"));
}

function toggleTheme() {
  const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem(themeState, nextTheme);
  applyTheme(nextTheme);
}

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
    showLoggedOut();
    if (currentTool === "profile") {
      openLoginPanel("登录状态已失效，请重新登录。", "error");
    }
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

function updateReportTypeFields() {
  const homeworkOnly = reportTypeSelect?.value === "homework";
  studentList?.classList.toggle("homework-only", homeworkOnly);
  const label = classProblemField?.firstChild;
  if (label && label.nodeType === Node.TEXT_NODE) label.textContent = homeworkOnly ? "作业题目" : "课堂题目";
  if (afterProblemField) afterProblemField.hidden = homeworkOnly;
  setProblemStatus(homeworkOnly ? "请选择本次需要检查的课后作业" : "请选择训练后加载题目");
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

function openLoginPanel(message = "", type = "info") {
  loginScreen.hidden = false;
  loginScreen.setAttribute("aria-hidden", "false");
  if (message) {
    setLoginStatus(message, type);
  } else {
    clearLoginStatus();
  }
  window.setTimeout(() => {
    const account = loginForm.elements.account;
    if (account) account.focus();
  }, 0);
}

function closeLoginPanel() {
  loginScreen.hidden = true;
  loginScreen.setAttribute("aria-hidden", "true");
}

function showLoggedOut() {
  isLoggedIn = false;
  document.body.dataset.authState = "logged-out";
  closeLoginPanel();
  appShell.hidden = false;
  currentUser.textContent = "未登录";
  userMenu.hidden = true;
  updateToolActions();
  closeUserMenu();
}

function showApp(account) {
  isLoggedIn = true;
  document.body.dataset.authState = "logged-in";
  closeLoginPanel();
  appShell.hidden = false;
  currentUser.textContent = account || "当前用户";
  userMenu.hidden = false;
  updateToolActions();
}

function updateToolActions() {
  const needsOj = toolMeta[currentTool]?.needsOj === true;
  userMenu.hidden = !needsOj || !isLoggedIn;
  openLoginBtn.hidden = !needsOj || isLoggedIn;
  generateReportBtn.hidden = !needsOj;
  generateReportBtn.disabled = needsOj && !isLoggedIn;
  if (userMenu.hidden) closeUserMenu();
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
  clearReportResult();
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
  setStudentStatus("登录 OJ 后加载学生");
  setSavedStudentsStatus("保存后，下次选择该团队会自动使用这份名单");
  setProblemStatus("登录 OJ 后选择团队和训练");
  setAfterProblemStatus("登录 OJ 后选择训练");
  clearReportStatus();
}

async function checkLogin() {
  try {
    const payload = await fetchJson("/api/me");
    if (payload.loggedIn) {
      showApp(payload.account);
      await loadTeams();
    } else {
      showLoggedOut();
    }
  } catch (error) {
    showLoggedOut();
    setProblemStatus(displayError(error));
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
    showLoggedOut();
  }
}

async function loadTeams() {
  if (!isLoggedIn) {
    setSelectOptions(teamSelect, [], "请先登录 OJ");
    setProblemStatus("登录 OJ 后加载团队");
    return;
  }
  try {
    const previousTeamId = teamSelect.value;
    const payload = await fetchJson("/api/teams");
    const options = payload.teams.map((team) =>
      option(`${team.name}（gid=${team.groupId}）`, String(team.groupId)),
    );
    setSelectOptions(teamSelect, options, "请选择团队");
    if (previousTeamId && options.some((item) => item.value === previousTeamId)) {
      teamSelect.value = previousTeamId;
    }
    if (teamSelect.value) {
      teamSelect.dispatchEvent(new Event("change"));
    }
    setProblemStatus(`已加载 ${payload.teams.length} 个团队`);
  } catch (error) {
    if (handleSessionError(error)) return;
    setSelectOptions(teamSelect, [], "团队加载失败");
    setProblemStatus(displayError(error, "团队加载失败，请稍后重试。"));
  }
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
  header.innerHTML = "<span></span><span>请假</span><span>real_name</span><span>nickname</span><span>user_name</span><span>school</span><span>phone</span>";
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

    const absentCheckbox = document.createElement("input");
    absentCheckbox.type = "checkbox";
    absentCheckbox.className = "absent-input";
    absentCheckbox.setAttribute("aria-label", `第 ${index + 1} 位学生请假`);

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

    row.append(checkbox, absentCheckbox, realNameInput, nickname, username, school, phone);
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

function selectedAbsentStudentUids() {
  return [...studentList.querySelectorAll(".student-row")]
    .filter((row) => row.querySelector(".absent-input")?.checked)
    .map((row) => row.dataset.uid)
    .filter(Boolean);
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
  const homeworkOnly = data.reportType === "homework";
  const team = clean(data.teamName || data.team, "必填：团队名称/gid/团队链接");
  const training = clean(data.trainingTitle || data.training, "必填：训练名称");
  const problems = clean(data.problems, "必填：题目名称或题号，逗号分隔");
  const afterClassProblems = String(data.afterClassProblems || "").trim();
  const trainingPassword = String(data.trainingPassword || "").trim();

  const checks = [
    data.team ? "- 团队已选择" : "- 请先选择团队",
    data.training ? "- 训练已选择" : "- 请先选择训练",
    data.problems ? (homeworkOnly ? "- 作业题目已选择" : "- 课堂题目已选择") : (homeworkOnly ? "- 请至少选择一道作业题目" : "- 请至少选择一道课堂题目"),
    homeworkOnly ? "- 类型：课后作业完成情况" : afterClassProblems
      ? "- 已选择课后题"
      : "- 未填写课后题：Excel 课后作业区域保持空白",
  ];

  return sentenceJoin([
    "# 学情反馈表",
    `## 当前选择\n- 团队：${team}\n- 训练：${training}\n- ${homeworkOnly ? "作业题目" : "课堂题目"}：${problems}`,
    `## 可选内容\n- 课后题：${afterClassProblems || "未填写"}\n- 训练密码：${trainingPassword ? "已填写" : "未填写"}`,
    `## 检查\n${checks.join("\n")}`,
  ]);
}

function selectedValues(container) {
  return [...container.querySelectorAll("input:checked")].map(
    (item) => item.dataset.problemId || item.value,
  );
}

function toggleAllCheckboxes(container, onChange) {
  const checkboxes = [...container.querySelectorAll("input[type='checkbox']")];
  const shouldCheck = checkboxes.some((item) => !item.checked);
  checkboxes.forEach((item) => {
    item.checked = shouldCheck;
  });
  onChange();
}

function setReportStatus(message, type = "info", autoHideMs = 0) {
  if (reportStatusHideTimer) {
    window.clearTimeout(reportStatusHideTimer);
    reportStatusHideTimer = null;
  }
  reportStatus.hidden = false;
  reportStatus.textContent = message;
  reportStatus.dataset.type = type;
  if (autoHideMs > 0) {
    reportStatusHideTimer = window.setTimeout(() => {
      if (reportStatus.textContent === message && reportStatus.dataset.type === type) {
        clearReportStatus();
      }
    }, autoHideMs);
  }
}

function clearReportStatus() {
  if (reportStatusHideTimer) {
    window.clearTimeout(reportStatusHideTimer);
    reportStatusHideTimer = null;
  }
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
  if (!isLoggedIn) {
    setReportStatus("生成学情表需要先登录 OJ。", "error");
    openLoginPanel("生成学情反馈表需要先登录 OJ。", "info");
    return;
  }
  const homeworkOnly = reportTypeSelect?.value === "homework";
  const payload = {
    teamId: teamSelect.value,
    trainingId: trainingSelect.value,
    trainingPassword: document.querySelector("#profileForm").elements.trainingPassword.value.trim(),
    problems: selectedValues(problemList),
    afterClassProblems: homeworkOnly ? [] : selectedValues(afterProblemList),
    homeworkOnly,
    absentStudentUids: homeworkOnly ? [] : selectedAbsentStudentUids(),
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
    setReportStatus(homeworkOnly ? "请至少选择一道作业题目" : "请至少选择一道课堂题目", "error");
    focusField("problems");
    return;
  }
  if (!(await ensureStudentsSavedForReport())) {
    return;
  }
  payload.studentsJson = studentsJsonInput.value;
  if (Object.keys(reportEdits).length && !window.confirm("当前表格有修改，重新生成会清除这些修改。继续生成？")) {
    return;
  }

  generateReportBtn.disabled = true;
  downloadReportBtn.disabled = true;
  generateReportBtn.textContent = "生成中...";
  setReportStatus("正在读取成绩并生成学情表。", "info");
  try {
    const result = await postJson("/api/reports", payload);
    renderReportResult(result);
    setReportStatus("学情表已生成。", "success", REPORT_SUCCESS_HIDE_MS);
  } catch (error) {
    if (handleSessionError(error)) return;
    setReportStatus(displayError(error, "学情表生成失败，请检查选择内容后重试。"), "error");
  } finally {
    generateReportBtn.disabled = !isLoggedIn;
    downloadReportBtn.disabled = false;
    generateReportBtn.textContent = "生成学情表";
  }
}

reportTypeSelect?.addEventListener("change", updateReportTypeFields);
updateReportTypeFields();

function clearReportResult() {
  currentReport = null;
  reportEdits = {};
  reportResult.hidden = true;
  reportTable.replaceChildren();
  document.querySelector("#profileForm").hidden = false;
  adjustReportBtn.textContent = "调整选择";
}

function exitReportPreview() {
  reportResult.hidden = true;
  const form = document.querySelector("#profileForm");
  form.hidden = false;
  adjustReportBtn.textContent = "调整选择";
  clearReportStatus();
  form.scrollIntoView({ block: "start" });
  reportTypeSelect?.focus({ preventScroll: true });
}

function buildReportTable(report, editable = false) {
  const table = document.createElement("table");
  const head = table.createTHead();
  const body = table.createTBody();
  report.cells.forEach((row, rowIndex) => {
    const tr = (rowIndex < 2 ? head : body).insertRow();
    row.forEach((cell, columnIndex) => {
      if (!cell) return;
      const td = document.createElement(rowIndex < 2 ? "th" : "td");
      td.rowSpan = cell.rowSpan;
      td.colSpan = cell.colSpan;
      const value = reportEdits[cell.coordinate] ?? cell.value;
      if (editable && cell.editable) {
        const editor = document.createElement("span");
        editor.className = "report-cell-editor";
        editor.contentEditable = "plaintext-only";
        editor.setAttribute("role", "textbox");
        const label = report.cells[1][columnIndex]?.value || report.cells[0][columnIndex]?.value || cell.coordinate;
        editor.setAttribute("aria-label", `${report.cells[rowIndex][0]?.value || "学生"} ${label}`);
        editor.setAttribute("aria-multiline", "true");
        editor.dataset.coordinate = cell.coordinate;
        editor.textContent = value;
        editor.addEventListener("input", () => {
          const nextValue = editor.innerText.replace(/\r\n/g, "\n");
          if (nextValue.length > 2000) {
            editor.textContent = reportEdits[cell.coordinate] ?? cell.value;
            setReportStatus("单元格内容长度上限为 2000 字。", "error");
            return;
          }
          if (nextValue === cell.value) delete reportEdits[cell.coordinate];
          else reportEdits[cell.coordinate] = nextValue;
          fitReportTable();
        });
        td.appendChild(editor);
      } else {
        td.textContent = value;
      }
      tr.appendChild(td);
    });
  });
  return table;
}

// 按窗口宽高缩放整张表，供截图使用；保留原列宽与可编辑内容。
function fitReportTable() {
  if (reportResult.hidden || !reportTable.rows.length) return;
  reportTable.style.zoom = "1";
  const bounds = reportTable.getBoundingClientRect();
  const availableWidth = reportTable.parentElement.clientWidth;
  const availableHeight = Math.max(1, window.innerHeight - bounds.top - 24);
  const scale = Math.min(1, availableWidth / bounds.width, availableHeight / bounds.height);
  reportTable.style.zoom = String(scale);
}

window.addEventListener("resize", fitReportTable);
new ResizeObserver(fitReportTable).observe(reportResult);

function renderReportResult(result) {
  if (!result || typeof result.reportId !== "string" || !result.reportId
      || !Array.isArray(result.cells) || result.cells.length < 2
      || !result.cells.every(Array.isArray)) {
    throw new Error("学情表数据不完整。请重启工具箱服务，刷新页面后重新生成。入口：http://127.0.0.1:8765");
  }
  currentReport = result;
  reportEdits = {};
  reportResultTitle.textContent = result.title;
  reportTable.replaceChildren(...buildReportTable(result, true).children);
  reportResult.hidden = false;
  document.querySelector("#profileForm").hidden = true;
  adjustReportBtn.textContent = "调整选择";
  reportResult.scrollIntoView({ block: "start" });
  fitReportTable();
}

async function copyReportTable() {
  if (!currentReport) return;
  copyReportBtn.disabled = true;
  try {
    const text = currentReport.cells.map((row) => row.map((cell) => {
      const value = cell ? reportEdits[cell.coordinate] ?? cell.value : "";
      return /[\t\n\r"]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
    }).join("\t")).join("\n");
    if (typeof ClipboardItem !== "undefined" && navigator.clipboard.write) {
      const html = buildReportTable(currentReport).outerHTML;
      await navigator.clipboard.write([new ClipboardItem({
        "text/plain": new Blob([text], { type: "text/plain" }),
        "text/html": new Blob([html], { type: "text/html" }),
      })]);
    } else {
      await navigator.clipboard.writeText(text);
    }
    setReportStatus("表格已复制。", "success", REPORT_SUCCESS_HIDE_MS);
  } catch (error) {
    setReportStatus("复制失败，请检查浏览器的剪贴板设置。", "error");
  } finally {
    copyReportBtn.disabled = false;
  }
}

async function downloadReport() {
  if (!currentReport) return;
  downloadReportBtn.disabled = true;
  generateReportBtn.disabled = true;
  try {
    const result = await postJson("/api/reports/export", {
      reportId: currentReport.reportId,
      edits: reportEdits,
    });
    const link = document.createElement("a");
    link.href = result.downloadUrl;
    link.download = result.filename || "";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setReportStatus("Excel 文件已生成，下载已触发。", "success", REPORT_SUCCESS_HIDE_MS);
  } catch (error) {
    if (handleSessionError(error)) return;
    setReportStatus(displayError(error, "Excel 下载失败，请重试。"), "error");
  } finally {
    downloadReportBtn.disabled = false;
    generateReportBtn.disabled = !isLoggedIn;
  }
}

function buildFeedbackPreview(data) {
  const topic = clean(data.topic, "课程主题");
  const knowledgePoints = clean(data.knowledgePoints, "本节知识点");
  const level = clean(data.level, "中等");
  return sentenceJoin([
    `# ${topic}课后反馈`,
    `## 生成设置\n- 默认表现：${level}\n- 知识点：${knowledgePoints}`,
    feedbackStudents.length
      ? `## 学生数量\n已加载 ${feedbackStudents.length} 名学生`
      : "## 学生数量\n未上传学生 JSON",
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
  persistDraftSnapshot();
}

function lineList(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function setFeedbackStatus(message) {
  if (!feedbackStatus) return;
  feedbackStatus.textContent = message;
}

function setFeedbackOcrStatus(message) {
  if (!feedbackOcrStatus) return;
  feedbackOcrStatus.textContent = message;
}

function feedbackOptions() {
  const data = getFormData("feedbackForm");
  return {
    topic: data.topic,
    knowledgePoints: data.knowledgePoints,
    level: data.level,
  };
}

function compressFeedbackKnowledge() {
  const form = document.querySelector("#feedbackForm");
  const field = form.elements.knowledgePoints;
  const compressed = FeedbackBuilder.compressKnowledgePoints(field.value);
  if (!compressed) {
    setFeedbackOcrStatus("请先填写要压缩的知识点。");
    field.focus();
    return;
  }
  field.value = compressed;
  setFeedbackOcrStatus("已压缩为短知识点列表。");
  generateOutput();
}

function renderFeedbackCheckResult(container, result) {
  container.replaceChildren();
  container.hidden = false;
  const summary = document.createElement("p");
  summary.className = "feedback-check-summary";
  summary.dataset.status = result.status || "needs_review";
  summary.textContent = result.summary || (result.status === "ok" ? "未发现明显问题。" : "检查完成。");
  container.appendChild(summary);

  const issues = Array.isArray(result.issues) ? result.issues : [];
  if (issues.length) {
    const list = document.createElement("ul");
    list.className = "feedback-check-list";
    issues.forEach((issue) => {
      const item = document.createElement("li");
      const message = issue.message || "发现一个问题";
      const quote = issue.quote ? ` 原文：${issue.quote}` : "";
      const suggestion = issue.suggestion ? ` 建议：${issue.suggestion}` : "";
      item.textContent = `[${issue.severity || "medium"}] ${message}${quote}${suggestion}`;
      list.appendChild(item);
    });
    container.appendChild(list);
  }

  const suggestions = Array.isArray(result.suggestions) ? result.suggestions : [];
  if (suggestions.length) {
    const advice = document.createElement("p");
    advice.className = "feedback-check-advice";
    advice.textContent = `整体建议：${suggestions.join("；")}`;
    container.appendChild(advice);
  }
}

async function checkFeedbackCard({ button, resultBox, student, body }) {
  const feedback = body.value.trim();
  if (!feedback) {
    resultBox.hidden = false;
    resultBox.textContent = "请先生成或填写要检查的反馈。";
    return;
  }
  const options = feedbackOptions();
  button.disabled = true;
  button.textContent = "检查中...";
  resultBox.hidden = false;
  resultBox.textContent = "正在交给 Codex agent 检查...";
  try {
    const result = await postJson("/api/feedback/check", {
      studentName: student.displayName,
      username: student.username,
      level: student.level || options.level,
      topic: options.topic,
      feedback,
    });
    renderFeedbackCheckResult(resultBox, result);
  } catch (error) {
    resultBox.textContent = displayError(error, "检查失败，请稍后重试。");
  } finally {
    button.disabled = false;
    button.textContent = "检查";
  }
}

function renderFeedbackList() {
  if (!feedbackList) return;
  feedbackList.replaceChildren();
  if (!feedbackStudents.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "还没有学生。请先上传学生 JSON。";
    feedbackList.appendChild(empty);
    return;
  }

  const defaults = feedbackOptions();
  feedbackStudents.forEach((student) => {
    student.level = student.level || defaults.level || "中等";
    student.dimensions = normalizeFeedbackDimensions(student.dimensions);
  });
  saveFeedbackStudentsState();
  feedbackStudents.forEach((student, index) => {
    const article = document.createElement("article");
    article.className = "feedback-card";

    const header = document.createElement("div");
    header.className = "feedback-card-header";

    const title = document.createElement("h3");
    title.textContent = `${index + 1}. ${student.displayName}`;

    const levelLabel = document.createElement("label");
    levelLabel.className = "feedback-level-select";
    levelLabel.textContent = "表现";

    const levelSelect = document.createElement("select");
    levelSelect.dataset.studentUid = student.uid;
    ["优秀", "中等", "差"].forEach((level) => {
      const option = document.createElement("option");
      option.value = level;
      option.textContent = level;
      levelSelect.appendChild(option);
    });
    levelSelect.value = student.level || defaults.level || "中等";
    levelSelect.addEventListener("change", () => {
      student.level = levelSelect.value;
      saveFeedbackStudentsState();
    });
    levelLabel.appendChild(levelSelect);

    const dimensionGrid = document.createElement("div");
    dimensionGrid.className = "feedback-dimension-grid";
    // configured dimensions: understanding / independence / classroomState / mainIssue

    FEEDBACK_DIMENSIONS.forEach((dimension) => {
      const wrapper = document.createElement("div");
      wrapper.className = "feedback-dimension-row";

      const topRow = document.createElement("div");
      topRow.className = "feedback-dimension-row-top";

      const name = document.createElement("span");
      name.className = "feedback-dimension-label";
      name.textContent = dimension.label;

      const includeLabel = document.createElement("label");
      includeLabel.className = "feedback-dimension-include";

      const includeInput = document.createElement("input");
      includeInput.type = "checkbox";
      includeInput.checked = student.dimensions?.[dimension.key]?.includeInFeedback !== false;
      includeInput.addEventListener("change", () => {
        student.dimensions = {
          ...student.dimensions,
          [dimension.key]: {
            ...(student.dimensions?.[dimension.key] || {}),
            includeInFeedback: includeInput.checked,
          },
        };
        saveFeedbackStudentsState();
      });

      const includeText = document.createElement("span");
      includeText.textContent = "写入反馈";
      includeLabel.append(includeInput, includeText);
      topRow.append(name, includeLabel);

      const select = document.createElement("select");
      const currentValue = student.dimensions?.[dimension.key]?.value || dimension.options[0];
      dimension.options.forEach((optionText) => {
        const option = document.createElement("option");
        option.value = optionText;
        option.textContent = optionText;
        select.appendChild(option);
      });
      select.value = currentValue;
      select.addEventListener("change", () => {
        student.dimensions = {
          ...(student.dimensions || {}),
          [dimension.key]: {
            ...(student.dimensions?.[dimension.key] || {}),
            value: select.value,
          },
        };
        saveFeedbackStudentsState();
      });
      wrapper.append(topRow, select);
      dimensionGrid.appendChild(wrapper);
    });

    const generateBtn = document.createElement("button");
    generateBtn.className = "mini-button feedback-generate-button";
    generateBtn.type = "button";
    generateBtn.textContent = "反馈";

    const checkBtn = document.createElement("button");
    checkBtn.className = "mini-button feedback-check-button";
    checkBtn.type = "button";
    checkBtn.textContent = "检查";

    const controls = document.createElement("div");
    controls.className = "feedback-card-controls";
    controls.append(levelLabel, generateBtn, checkBtn);
    header.append(title, controls);

    const meta = document.createElement("p");
    meta.className = "feedback-student-meta";
    meta.textContent = student.username ? `账号：${student.username}` : "账号：未提供";

    const detailsLabel = document.createElement("label");
    detailsLabel.className = "feedback-details-label";
    detailsLabel.textContent = "课堂细节描述";

    const details = document.createElement("textarea");
    details.className = "feedback-details-input";
    details.rows = 4;
    details.placeholder =
      "填写真实课堂细节，例如：提问到 global 时能回答出来；写碰撞检测时需要提示；后半节注意力有所下降。Agent 会按本地 skill 整理成反馈。";
    details.value = student.details || "";
    details.addEventListener("input", () => {
      student.details = details.value;
      saveFeedbackStudentsState();
    });
    detailsLabel.appendChild(details);

    const body = document.createElement("textarea");
    body.className = "feedback-result-input";
    body.rows = 8;
    body.value = student.feedback || "";
    body.addEventListener("input", () => {
      student.feedback = body.value;
      saveFeedbackStudentsState();
    });

    const resultLabel = document.createElement("div");
    resultLabel.className = "feedback-result-label";
    resultLabel.textContent = "私人反馈";

    const chat = document.createElement("section");
    chat.className = "feedback-chat";

    const chatTitle = document.createElement("h4");
    chatTitle.textContent = "和 Agent 沟通修改";

    const chatMessages = document.createElement("div");
    chatMessages.className = "feedback-chat-messages";
    chatMessages.setAttribute("aria-live", "polite");

    const renderChatMessages = () => {
      chatMessages.replaceChildren();
      const history = Array.isArray(student.chatHistory) ? student.chatHistory : [];
      if (!history.length) {
        const empty = document.createElement("p");
        empty.className = "feedback-chat-empty";
        empty.textContent = "可以直接说：压缩一点、语气温和些、突出主动回答的问题。";
        chatMessages.appendChild(empty);
        return;
      }
      history.forEach((item) => {
        const message = document.createElement("p");
        message.className = `feedback-chat-message ${item.role === "assistant" ? "is-agent" : "is-user"}`;
        message.textContent = `${item.role === "assistant" ? "Agent" : "我"}：${item.text}`;
        chatMessages.appendChild(message);
      });
    };

    const chatInput = document.createElement("textarea");
    chatInput.className = "feedback-chat-input";
    chatInput.rows = 2;
    chatInput.placeholder = "告诉 Agent 怎样修改这条反馈，例如：再简短一点，少写套话";

    const reviseBtn = document.createElement("button");
    reviseBtn.className = "mini-button feedback-revise-button";
    reviseBtn.type = "button";
    reviseBtn.textContent = "发送并修改";
    reviseBtn.addEventListener("click", () => {
      reviseFeedbackForStudent({ button: reviseBtn, student, body, input: chatInput, messages: chatMessages, renderMessages: renderChatMessages });
    });
    chatInput.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        reviseBtn.click();
      }
    });
    renderChatMessages();
    chat.append(chatTitle, chatMessages, chatInput, reviseBtn);

    const checkResult = document.createElement("div");
    checkResult.className = "feedback-check-result";
    checkResult.hidden = true;
    generateBtn.addEventListener("click", () => {
      generateFeedbackForStudent({ button: generateBtn, student, body, resultBox: checkResult });
    });
    checkBtn.addEventListener("click", () => {
      checkFeedbackCard({ button: checkBtn, resultBox: checkResult, student, body });
    });

    article.append(header, meta, dimensionGrid, detailsLabel, checkResult, resultLabel, body, chat);
    feedbackList.appendChild(article);
  });
}

async function importFeedbackJsonFile(file) {
  if (!file) return;
  try {
    const payload = JSON.parse(await file.text());
    const defaultLevel = feedbackOptions().level || "中等";
    feedbackStudents = FeedbackBuilder.parseStudentJson(payload).map((student) =>
      normalizeFeedbackStudentState(
        {
          ...student,
          level: defaultLevel,
          dimensions: buildDefaultFeedbackDimensions(),
          details: "",
          feedback: "",
          chatHistory: [],
        },
        defaultLevel,
      ),
    );
    if (!feedbackStudents.length) {
      throw new Error("JSON 中没有可用学生。");
    }
    saveFeedbackStudentsState();
    setFeedbackStatus(`已加载 ${feedbackStudents.length} 名学生，请按学生逐个生成反馈。`);
    renderFeedbackList();
  } catch (error) {
    feedbackStudents = [];
    saveFeedbackStudentsState();
    setFeedbackStatus(error && error.message ? error.message : "学生 JSON 解析失败。");
    renderFeedbackList();
  } finally {
    feedbackJsonUploadInput.value = "";
  }
}

async function generateFeedbackForStudent({ button, student, body, resultBox }) {
  const options = feedbackOptions();
  button.disabled = true;
  button.textContent = "生成中...";
  setFeedbackStatus(`正在为 ${student.displayName} 生成反馈，Agent 运行中...`);
  resultBox.hidden = true;
  resultBox.textContent = "";
  try {
    const payload = await postJson("/api/feedback/generate", {
      studentName: student.displayName,
      username: student.username,
      level: student.level || options.level,
      details: student.details || "",
      dimensions: Object.fromEntries(
        FEEDBACK_DIMENSIONS.map((dimension) => [
          dimension.key,
          {
            value: student.dimensions?.[dimension.key]?.value || dimension.options[0],
            include: student.dimensions?.[dimension.key]?.includeInFeedback !== false,
          },
        ]),
      ),
    });
    student.feedback = payload.feedback || "";
    body.value = student.feedback;
    saveFeedbackStudentsState();
    setFeedbackStatus(`${student.displayName} 的反馈已生成。`);
    resultBox.hidden = true;
  } catch (error) {
    setFeedbackStatus(displayError(error, "反馈生成失败，请稍后重试。"));
    resultBox.textContent = displayError(error, "反馈生成失败，请稍后重试。");
  } finally {
    button.disabled = false;
    button.textContent = "反馈";
  }
}

async function reviseFeedbackForStudent({ button, student, body, input, messages, renderMessages }) {
  const instruction = input.value.trim();
  if (!instruction) {
    input.focus();
    return;
  }
  const feedback = body.value.trim();
  if (!feedback) {
    setFeedbackStatus("请先生成或填写反馈，再告诉 Agent 怎样修改。");
    body.focus();
    return;
  }
  student.chatHistory = Array.isArray(student.chatHistory) ? student.chatHistory : [];
  student.chatHistory.push({ role: "user", text: instruction });
  student.chatHistory = student.chatHistory.slice(-20);
  input.value = "";
  renderMessages();
  saveFeedbackStudentsState();
  button.disabled = true;
  button.textContent = "修改中...";
  setFeedbackStatus(`正在按你的要求修改 ${student.displayName} 的反馈...`);
  try {
    const payload = await postJson("/api/feedback/revise", {
      feedback,
      instruction,
      details: student.details || "",
      level: student.level || "中等",
      dimensions: Object.fromEntries(
        FEEDBACK_DIMENSIONS.map((dimension) => [
          dimension.key,
          {
            value: student.dimensions?.[dimension.key]?.value || dimension.options[0],
            include: student.dimensions?.[dimension.key]?.includeInFeedback !== false,
          },
        ]),
      ),
    });
    student.feedback = payload.feedback || feedback;
    body.value = student.feedback;
    student.chatHistory.push({ role: "assistant", text: payload.message || "已按要求修改。" });
    student.chatHistory = student.chatHistory.slice(-20);
    renderMessages();
    saveFeedbackStudentsState();
    setFeedbackStatus(`${student.displayName} 的反馈已修改。`);
  } catch (error) {
    student.chatHistory.push({ role: "assistant", text: displayError(error, "修改失败，请重试。") });
    renderMessages();
    saveFeedbackStudentsState();
    setFeedbackStatus(displayError(error, "反馈修改失败，请稍后重试。"));
  } finally {
    button.disabled = false;
    button.textContent = "发送并修改";
  }
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(reader.result));
    reader.addEventListener("error", () => reject(new Error("图片读取失败，请重新上传。")));
    reader.readAsDataURL(file);
  });
}

function showFeedbackScreenshotPreview(imageData) {
  if (!feedbackScreenshotPreview || !feedbackScreenshotImage) return;
  feedbackScreenshotImage.src = imageData;
  feedbackScreenshotPreview.hidden = false;
}

function clearPendingFeedbackScreenshot() {
  pendingFeedbackScreenshot = null;
  if (feedbackScreenshotImage) {
    feedbackScreenshotImage.removeAttribute("src");
  }
  if (feedbackScreenshotPreview) {
    feedbackScreenshotPreview.hidden = true;
  }
  if (confirmFeedbackScreenshotBtn) {
    confirmFeedbackScreenshotBtn.disabled = true;
  }
  setFeedbackOcrStatus("已删除课堂截图，可重新粘贴或选择截图。");
}

async function stageFeedbackScreenshot(file) {
  if (!file) return;
  try {
    const imageData = await readFileAsDataUrl(file);
    pendingFeedbackScreenshot = {
      file,
      imageData,
    };
    showFeedbackScreenshotPreview(imageData);
    confirmFeedbackScreenshotBtn.disabled = false;
    setFeedbackOcrStatus("截图已放入本节知识点框内，确认后再上传给 Codex agent 总结。");
  } catch (error) {
    setFeedbackOcrStatus(displayError(error, "图片读取失败，请重新选择或粘贴。"));
  } finally {
    feedbackScreenshotInput.value = "";
  }
}

async function summarizePendingFeedbackScreenshot() {
  if (!pendingFeedbackScreenshot) {
    setFeedbackOcrStatus("请先粘贴或选择课堂截图。");
    return;
  }
  uploadFeedbackScreenshotBtn.disabled = true;
  confirmFeedbackScreenshotBtn.disabled = true;
  confirmFeedbackScreenshotBtn.textContent = "总结中...";
  setFeedbackOcrStatus("正在交给 Codex agent 识别并总结...");
  try {
    const imageData = pendingFeedbackScreenshot.imageData;
    const payload = await postJson("/api/feedback/summarize-image", { imageData });
    const form = document.querySelector("#feedbackForm");
    if (payload.topic) {
      form.elements.topic.value = payload.topic;
    }
    if (payload.knowledgePoints) {
      form.elements.knowledgePoints.value = payload.knowledgePoints;
    }
    feedbackScreenshotPreview.hidden = true;
    feedbackAgentSummary.hidden = false;
    feedbackAgentSummary.value = payload.summary || "";
    setFeedbackOcrStatus("Codex agent 已总结截图，并填入课程主题和知识点。");
    generateOutput();
  } catch (error) {
    setFeedbackOcrStatus(displayError(error, "Codex agent 总结失败，请换一张更清晰的截图。"));
  } finally {
    uploadFeedbackScreenshotBtn.disabled = false;
    confirmFeedbackScreenshotBtn.disabled = false;
    confirmFeedbackScreenshotBtn.textContent = "确认上传给 Codex 总结";
  }
}

function handleFeedbackPaste(event) {
  if (currentTool !== "feedback") return;
  const imageFile = FeedbackBuilder.findPastedImageFile(event);
  if (!imageFile) return;
  event.preventDefault();
  stageFeedbackScreenshot(imageFile);
}

function switchTool(tool) {
  currentTool = tool;
  toolTitle.textContent = toolMeta[tool].title;
  closeLoginPanel();
  navButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tool === tool);
  });
  toolViews.forEach((view) => {
    view.classList.toggle("active", view.dataset.toolView === tool);
  });
  restoreDraft();
  if (tool === "profile" && teamSelect.value) {
    teamSelect.dispatchEvent(new Event("change"));
  }
  generateOutput();
  updateToolActions();
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
  persistDraftSnapshot();
  showToast("草稿已保存");
}

function persistDraftSnapshot() {
  const meta = toolMeta[currentTool];
  const data = getFormData(meta.formId);
  localStorage.setItem(draftKey(), JSON.stringify(data));
  if (saveState) saveState.textContent = "草稿已保存";
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

function buildDefaultFeedbackDimensions() {
  return Object.fromEntries(
    FEEDBACK_DIMENSIONS.map((dimension) => [
      dimension.key,
      {
        value: dimension.options[0],
        includeInFeedback: true,
      },
    ]),
  );
}

function normalizeFeedbackDimensionState(key, value) {
  const dimension = FEEDBACK_DIMENSIONS.find((item) => item.key === key);
  const fallback = dimension ? dimension.options[0] : "";
  if (!dimension) {
    return {
      value: String(value && value.value ? value.value : value || "").trim() || fallback,
      includeInFeedback: Boolean(
        value && typeof value === "object" && "includeInFeedback" in value
          ? value.includeInFeedback
          : value && typeof value === "object" && "include" in value
            ? value.include
            : true,
      ),
    };
  }
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const nextValue = String(value.value || "").trim();
    return {
      value: dimension.options.includes(nextValue) ? nextValue : fallback,
      includeInFeedback: Boolean(
        "includeInFeedback" in value ? value.includeInFeedback : "include" in value ? value.include : true,
      ),
    };
  }
  const legacyValue = String(value || "").trim();
  return {
    value: dimension.options.includes(legacyValue) ? legacyValue : fallback,
    includeInFeedback: true,
  };
}

function normalizeFeedbackDimensions(dimensions) {
  const source = dimensions && typeof dimensions === "object" ? dimensions : {};
  return Object.fromEntries(
    FEEDBACK_DIMENSIONS.map((dimension) => [
      dimension.key,
      normalizeFeedbackDimensionState(dimension.key, source[dimension.key]),
    ]),
  );
}

function normalizeFeedbackStudentState(student, fallbackLevel = "中等") {
  return {
    uid: String(student.uid || student.username || student.displayName || "").trim(),
    displayName: String(student.displayName || student.realName || student.nickname || student.username || "学生").trim(),
    username: String(student.username || "").trim(),
    level: String(student.level || "").trim() || fallbackLevel,
    dimensions: normalizeFeedbackDimensions(student.dimensions),
    details: String(student.details || "").trim(),
    feedback: String(student.feedback || "").trim(),
    chatHistory: Array.isArray(student.chatHistory) ? student.chatHistory.slice(-20) : [],
  };
}

function saveFeedbackStudentsState() {
  if (!feedbackStudents.length) {
    localStorage.removeItem(feedbackStudentsState);
    return;
  }
  localStorage.setItem(
    feedbackStudentsState,
    JSON.stringify({
      version: 2,
      students: feedbackStudents.map((student) => ({
        uid: student.uid,
        displayName: student.displayName,
        username: student.username,
        level: student.level,
        dimensions: student.dimensions,
        details: student.details || "",
        feedback: student.feedback || "",
        chatHistory: Array.isArray(student.chatHistory) ? student.chatHistory.slice(-20) : [],
      })),
    }),
  );
}

function restoreFeedbackStudentsState() {
  const raw = localStorage.getItem(feedbackStudentsState);
  if (!raw) return false;
  try {
    const payload = JSON.parse(raw);
    const students = Array.isArray(payload) ? payload : payload && payload.students;
    if (!Array.isArray(students) || !students.length) {
      localStorage.removeItem(feedbackStudentsState);
      return false;
    }
    const defaultLevel = feedbackOptions().level || "中等";
    feedbackStudents = students
      .map((student) => normalizeFeedbackStudentState(student, defaultLevel))
      .filter((student) => student.uid && student.displayName);
    if (!feedbackStudents.length) {
      localStorage.removeItem(feedbackStudentsState);
      return false;
    }
    setFeedbackStatus(`已恢复 ${feedbackStudents.length} 名学生的反馈草稿。`);
    return true;
  } catch (_error) {
    localStorage.removeItem(feedbackStudentsState);
    return false;
  }
}

function clampSidebarWidth(value) {
  return Math.min(SIDEBAR_WIDTH_MAX, Math.max(SIDEBAR_WIDTH_MIN, value));
}

function applySidebarWidth(width) {
  const next = clampSidebarWidth(width);
  document.documentElement.style.setProperty("--sidebar-width", `${next}px`);
  localStorage.setItem(sidebarWidthState, String(next));
}

function restoreSidebarWidth() {
  const raw = localStorage.getItem(sidebarWidthState);
  if (!raw) return;
  const width = Number(raw);
  if (!Number.isFinite(width)) return;
  applySidebarWidth(width);
}

function updateSidebarWidthFromClientX(clientX) {
  if (window.innerWidth <= 920) return;
  applySidebarWidth(clientX);
}

function stopSidebarResize() {
  if (!sidebarResizeSession) return;
  document.body.dataset.sidebarResizing = "false";
  window.removeEventListener("pointermove", sidebarResizeSession.onMove);
  window.removeEventListener("pointerup", sidebarResizeSession.onUp);
  window.removeEventListener("pointercancel", sidebarResizeSession.onUp);
  sidebarResizeSession = null;
}

function startSidebarResize(event) {
  if (!sidebarResizeHandle || window.innerWidth <= 920) return;
  event.preventDefault();
  sidebarResizeHandle.setPointerCapture?.(event.pointerId);
  document.body.dataset.sidebarResizing = "true";
  const onMove = (moveEvent) => updateSidebarWidthFromClientX(moveEvent.clientX);
  const onUp = () => stopSidebarResize();
  sidebarResizeSession = { onMove, onUp };
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp);
  window.addEventListener("pointercancel", onUp);
  updateSidebarWidthFromClientX(event.clientX);
}

function handleSidebarResizeKeydown(event) {
  if (window.innerWidth <= 920) return;
  const current = Number.parseInt(
    getComputedStyle(document.documentElement).getPropertyValue("--sidebar-width"),
    10,
  ) || 280;
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    applySidebarWidth(current - 16);
  }
  if (event.key === "ArrowRight") {
    event.preventDefault();
    applySidebarWidth(current + 16);
  }
}

navButtons.forEach((button) => {
  button.addEventListener("click", () => switchTool(button.dataset.tool));
});

document.querySelectorAll("form").forEach((form) => {
  form.addEventListener("input", (event) => {
    if (form.id === "feedbackForm" && event.target.closest("#feedbackList")) return;
    generateOutput();
  });
  form.addEventListener("change", (event) => {
    if (form.id === "feedbackForm" && event.target.closest("#feedbackList")) return;
    generateOutput();
  });
});

loginForm.addEventListener("submit", login);
openLoginBtn.addEventListener("click", () => openLoginPanel());
cancelLoginBtn.addEventListener("click", closeLoginPanel);
userMenuBtn.addEventListener("click", toggleUserMenu);
logoutBtn.addEventListener("click", logout);
themeToggleBtn.addEventListener("click", toggleTheme);
document.addEventListener("click", (event) => {
  if (!userMenu.contains(event.target)) closeUserMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeUserMenu();
});
document.addEventListener("paste", handleFeedbackPaste);
sidebarResizeHandle?.addEventListener("pointerdown", startSidebarResize);
sidebarResizeHandle?.addEventListener("keydown", handleSidebarResizeKeydown);
document.querySelector("#saveDraftBtn")?.addEventListener("click", saveDraft);
generateReportBtn.addEventListener("click", generateReport);
copyReportBtn.addEventListener("click", copyReportTable);
downloadReportBtn.addEventListener("click", downloadReport);
exitReportBtn?.addEventListener("click", exitReportPreview);
adjustReportBtn.addEventListener("click", () => {
  const form = document.querySelector("#profileForm");
  form.hidden = !form.hidden;
  adjustReportBtn.textContent = form.hidden ? "调整选择" : "收起选择";
  if (!form.hidden) form.scrollIntoView({ block: "start" });
});
uploadFeedbackJsonBtn.addEventListener("click", () => feedbackJsonUploadInput.click());
feedbackJsonUploadInput.addEventListener("change", () => {
  importFeedbackJsonFile(feedbackJsonUploadInput.files[0]);
});
uploadFeedbackScreenshotBtn.addEventListener("click", () => feedbackScreenshotInput.click());
feedbackScreenshotInput.addEventListener("change", () => {
  stageFeedbackScreenshot(feedbackScreenshotInput.files[0]);
});
compressKnowledgeBtn.addEventListener("click", compressFeedbackKnowledge);
confirmFeedbackScreenshotBtn.addEventListener("click", summarizePendingFeedbackScreenshot);
removeFeedbackScreenshotBtn.addEventListener("click", clearPendingFeedbackScreenshot);
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

document.body.dataset.authState = "checking";
document.body.dataset.sidebarResizing = "false";
restoreTheme();
appShell.hidden = false;
if (currentTool === "feedback") {
  restoreDraft();
  restoreFeedbackStudentsState();
  renderFeedbackList();
}
restoreSidebarWidth();
checkLogin();
generateOutput();
