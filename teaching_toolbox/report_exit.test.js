const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(process.argv[2] || `${__dirname}/app.js`, "utf8");
const body = source.match(/function exitReportPreview\(\) \{[\s\S]*?\n\}/);
if (!body) {
  console.log("EXIT_MISSING");
  process.exit(0);
}
const form = { hidden: true, scrollIntoView() {} };
const report = { reportId: "existing" };
const edits = { B3: "修改内容" };
const context = {
  reportResult: { hidden: false }, currentReport: report, reportEdits: edits,
  document: { querySelector: () => form },
  adjustReportBtn: { textContent: "收起选择" },
  clearReportStatus() {}, reportTypeSelect: { focus() {} },
};
vm.createContext(context);
vm.runInContext(body[0], context);
context.exitReportPreview();
assert.equal(context.reportResult.hidden, true);
assert.equal(form.hidden, false);
assert.equal(context.currentReport, report);
assert.equal(context.reportEdits, edits);
assert.equal(context.adjustReportBtn.textContent, "调整选择");
console.log("EXIT_PASS: preview_hidden=true; form_visible=true; edits_preserved=true");
