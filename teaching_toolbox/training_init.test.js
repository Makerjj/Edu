const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(process.argv[2] || path.join(__dirname, "app.js"), "utf8");
const definitions = ["loadTeams", "switchTool"].map((name) => {
  const match = source.match(new RegExp(`(?:async )?function ${name}\\([^]*?\\n\\}`));
  assert.ok(match, `缺少函数 ${name}`);
  return match[0];
}).join("\n");

async function check() {
  const calls = [];
  const select = {
    value: "2284",
    dispatchEvent: (event) => calls.push(event.type),
  };
  const context = vm.createContext({
    isLoggedIn: true,
    currentTool: "feedback",
    toolTitle: {},
    toolMeta: { profile: { title: "学情反馈表" }, feedback: { title: "课后反馈" } },
    teamSelect: select,
    navButtons: [],
    toolViews: [],
    Event: class { constructor(type) { this.type = type; } },
    fetchJson: async () => ({ teams: [{ groupId: 2284, name: "测试班" }] }),
    option: (label, value) => ({ label, value }),
    setSelectOptions: (element) => { element.value = ""; },
    setProblemStatus() {},
    handleSessionError: () => false,
    displayError: (error) => error.message,
    closeLoginPanel() {},
    restoreDraft: () => { select.value = "2284"; },
    generateOutput() {},
    updateToolActions() {},
    loadAgentStudio() {},
  });
  vm.runInContext(definitions, context);
  await vm.runInContext("loadTeams()", context);
  assert.equal(select.value, "2284", "团队列表刷新后保留有效选中项");
  assert.deepEqual(calls, ["change"], "恢复团队后触发训练加载");
  calls.length = 0;
  vm.runInContext('switchTool("profile")', context);
  assert.deepEqual(calls, ["change"], "切换学情表后触发训练加载");
  calls.length = 0;
  vm.runInContext('switchTool("feedback")', context);
  assert.deepEqual(calls, [], "其他工具不触发训练加载");
  select.value = "removed";
  await vm.runInContext("loadTeams()", context);
  assert.equal(select.value, "", "不存在的团队不恢复");
  assert.deepEqual(calls, [], "无团队时不触发训练加载");
  context.isLoggedIn = false;
  select.value = "2284";
  await vm.runInContext("loadTeams()", context);
  assert.deepEqual(calls, [], "退出状态不触发训练加载");
  console.log("TRAINING_INIT_PASS: refresh=1; profile=1; feedback=0; missing=0; logged_out=0");
}

check().catch((error) => { console.error(error.message); process.exitCode = 1; });
