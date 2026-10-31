const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(process.argv[2] || path.join(__dirname, "app.js"), "utf8");
const render = source.match(/function renderReportResult\(result\) \{[\s\S]*?\n\}/)[0];

function makeContext() {
  const form = { hidden: true };
  const oldReport = { reportId: "existing-report" };
  const oldEdits = { C3: "已有修改" };
  const context = {
    currentReport: oldReport,
    reportEdits: oldEdits,
    reportResultTitle: { textContent: "已有学情表" },
    reportResult: { hidden: false, scrollIntoView() {} },
    adjustReportBtn: { textContent: "收起选择" },
    reportTable: { replaced: false, replaceChildren() { this.replaced = true; } },
    document: { querySelector() { return form; } },
    fitReportTable() {},
    buildReportTable(result) {
      result.cells.forEach((row) => row.forEach(() => {}));
      return { children: [] };
    },
  };
  vm.createContext(context);
  vm.runInContext(render, context);
  return { context, oldReport, oldEdits };
}

if (process.argv[3] === "baseline") {
  const { context, oldReport } = makeContext();
  let error;
  try {
    context.renderReportResult({ downloadUrl: "/api/downloads/legacy", filename: "result.xlsx" });
  } catch (caught) { error = caught; }
  assert.equal(error?.message, "Cannot read properties of undefined (reading 'forEach')");
  assert.notEqual(context.currentReport, oldReport);
  console.log("BASELINE: TypeError: Cannot read properties of undefined (reading 'forEach'); state_preserved=false");
} else {
  const invalidResults = [
    { downloadUrl: "/api/downloads/legacy", filename: "result.xlsx" },
    null, {}, { reportId: "id", cells: "invalid" },
    { reportId: "id", cells: [] },
    { reportId: "id", cells: [[], null] },
    { reportId: "", cells: [[], []] },
  ];
  for (const result of invalidResults) {
    const { context, oldReport, oldEdits } = makeContext();
    assert.throws(() => context.renderReportResult(result), /请重启工具箱服务/);
    assert.equal(context.currentReport, oldReport);
    assert.equal(context.reportEdits, oldEdits);
    assert.equal(context.reportResultTitle.textContent, "已有学情表");
    assert.equal(context.reportTable.replaced, false);
  }
  const { context } = makeContext();
  const validResult = { reportId: "new-report", title: "新学情表", cells: [[], [], []] };
  context.renderReportResult(validResult);
  assert.equal(context.currentReport, validResult);
  assert.equal(context.reportResultTitle.textContent, "新学情表");
  assert.equal(context.reportTable.replaced, true);
  assert.equal(Object.keys(context.reportEdits).length, 0);
  console.log("REPORT_RESPONSE_PASS: invalid=7; state_preserved=7; valid=1");
}
