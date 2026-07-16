import fs from "node:fs";
import path from "node:path";

const repoRoot = process.cwd();
const ledgerPath = path.join(repoRoot, "PRIVATE", "app-standardization-ui-dogfood", "runs", "step15-live-dogfood-ledger.json");
const ledger = JSON.parse(fs.readFileSync(ledgerPath, "utf8"));
const expectedTaskIds = [
  "DG-CHAT-CODEFIX-01",
  "DG-MULTIMODAL-UI-01",
  "DG-GRAPH-PARALLEL-01",
  "DG-AUTOMATION-HANDOFF-01",
];
const requiredTaskFields = [
  "id",
  "surface",
  "fixture",
  "prompt_file",
  "capability_requirements",
  "preferred_route",
  "fallback_route",
  "max_requests",
  "token_budget",
  "retry_limit",
  "expected_artifacts",
  "abort_rules",
  "screenshot_checkpoints",
];
const forbiddenSecretPattern = /(api[_-]?key|authorization|bearer|password|cookie)\s*[:=]\s*[^\s"']+/i;
const errors = [];

if (ledger.schema_version !== "astrabridge-live-dogfood-ledger-v1") {
  errors.push("Unexpected ledger schema_version.");
}
if (ledger.tasks?.length !== expectedTaskIds.length) {
  errors.push("Ledger must declare exactly four dogfood tasks.");
}

for (const taskId of expectedTaskIds) {
  const task = ledger.tasks?.find((candidate) => candidate.id === taskId);
  if (!task) {
    errors.push(`Missing task ${taskId}.`);
    continue;
  }
  for (const field of requiredTaskFields) {
    if (task[field] == null || (Array.isArray(task[field]) && task[field].length === 0)) {
      errors.push(`${taskId} is missing ${field}.`);
    }
  }
  for (const localPath of [task.fixture, task.prompt_file]) {
    if (!fs.existsSync(path.join(repoRoot, localPath))) {
      errors.push(`${taskId} references a missing local path: ${localPath}`);
    }
  }
  if (task.token_budget <= 0 || task.max_requests <= 0) {
    errors.push(`${taskId} must use positive request and token limits.`);
  }
}

const serialized = JSON.stringify(ledger);
if (forbiddenSecretPattern.test(serialized)) {
  errors.push("Ledger contains a secret-like assignment.");
}

if (errors.length > 0) {
  console.error(JSON.stringify({ status: "failed", errors }, null, 2));
  process.exit(1);
}

console.log(JSON.stringify({
  status: "passed",
  schema_version: ledger.schema_version,
  task_ids: expectedTaskIds,
  provider_calls: ledger.usage.provider_calls,
  note: "Read-only harness validation only; no provider call was attempted."
}, null, 2));
