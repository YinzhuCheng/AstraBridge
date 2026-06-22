import { describe, expect, it } from "vitest";

import type { IsolationAuditResponse, ProjectFile } from "../../types";
import { isolationAuditSummary, projectCaptureRoot, suggestedDogfoodScreenshotPath } from "./isolationAudit";

function buildProject(overrides: Partial<ProjectFile> = {}): ProjectFile {
  return {
    schema_version: "astrabridge-project-v1",
    project_id: "demo",
    name: "Demo",
    project_file: "D:\\AstraBridge\\PRIVATE\\demo.abproj",
    workspace_root: "D:\\AstraBridge\\PRIVATE\\workspace",
    entry_mode: "existing",
    default_profile_id: "deepseek-default",
    default_model: "deepseek-v4-pro",
    default_effort: "high",
    current_thread_id: null,
    recent_threads: [],
    ui_preferences: {},
    created_at: "2026-06-22T00:00:00Z",
    updated_at: "2026-06-22T00:00:00Z",
    ...overrides,
  };
}

describe("isolation audit helpers", () => {
  it("derives the workspace-local capture root", () => {
    expect(projectCaptureRoot(buildProject())).toBe("D:\\AstraBridge\\PRIVATE\\workspace\\.astrabridge\\captures");
    expect(projectCaptureRoot(null)).toBe("");
  });

  it("suggests a workspace-local screenshot path", () => {
    expect(suggestedDogfoodScreenshotPath(buildProject(), "Native Kernel Smoke")).toBe(
      "D:\\AstraBridge\\PRIVATE\\workspace\\.astrabridge\\captures\\native-kernel-smoke.png",
    );
  });

  it("summarizes passing and failing audit checks", () => {
    const audit: IsolationAuditResponse = {
      ok: false,
      checks: [
        { name: "workspace_storage_policy_exists", ok: true },
        { name: "workspace_no_old_lcr_state", ok: false, detail: "D:\\AstraBridge\\PRIVATE\\workspace\\.lcr" },
      ],
      paths: {},
      official_codex: { exists: false, managed_by_app: false, router_configured: false, config_sha256: null },
      ports: {},
      process_boundary: { app_server_running: false, codex_cli: null, execution_host: "windows" },
    };

    expect(isolationAuditSummary(audit)).toEqual({
      total: 2,
      passed: 1,
      failed: 1,
      failedChecks: [{ name: "workspace_no_old_lcr_state", ok: false, detail: "D:\\AstraBridge\\PRIVATE\\workspace\\.lcr" }],
    });
  });
});
