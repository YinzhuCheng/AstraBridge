import { describe, expect, it } from "vitest";

import type { ProjectSummary } from "../../types";
import { recentProjectCompactLocation, recentProjectDisplayName, recentProjectHoverDetail, recentProjectTooltip } from "./recentProjectCards";

function buildProject(overrides: Partial<ProjectSummary> = {}): ProjectSummary {
  return {
    project_id: "demo",
    name: "Provider Switch Live 20260622-224524",
    project_file: "D:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/demo.abproj",
    workspace_root: "D:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace",
    entry_mode: "new",
    updated_at: "2026-07-11T15:52:21.351304+09:00",
    ...overrides,
  };
}

describe("recentProjectCards", () => {
  it("keeps only the first non-empty line of the project name", () => {
    const project = buildProject({
      name: "Provider Switch Live 20260622-224524\nD:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace",
    });

    expect(recentProjectDisplayName(project)).toBe("Provider Switch Live 20260622-224524");
  });

  it("falls back to the project file stem when the name is blank", () => {
    const project = buildProject({ name: "   " });

    expect(recentProjectDisplayName(project)).toBe("demo");
  });

  it("strips inline path suffixes from legacy project names", () => {
    const project = buildProject({
      name: "Provider Switch Live 20260622-224524 D:\\AstraBridge\\PRIVATE\\demo-runs\\provider-switch-live-20260622-224524\\workspace",
    });

    expect(recentProjectDisplayName(project)).toBe("Provider Switch Live 20260622-224524");
  });

  it("strips inline forward-slash path suffixes from legacy project names", () => {
    const project = buildProject({
      name: "Provider Switch Live 20260622-224524 /Users/demo/provider-switch-live-20260622-224524/workspace",
    });

    expect(recentProjectDisplayName(project)).toBe("Provider Switch Live 20260622-224524");
  });

  it("keeps slash-delimited titles that are not filesystem paths", () => {
    const project = buildProject({
      name: "Provider Update / Smoke / Gate",
    });

    expect(recentProjectDisplayName(project)).toBe("Provider Update / Smoke / Gate");
  });

  it("falls back when the stored name is only a path fragment", () => {
    const project = buildProject({
      name: "D:\\AstraBridge\\PRIVATE\\demo-runs\\provider-switch-live-20260622-224524\\workspace",
    });

    expect(recentProjectDisplayName(project)).toBe("demo");
  });

  it("skips path-only lines and keeps the first readable title line", () => {
    const project = buildProject({
      name: "D:\\AstraBridge\\PRIVATE\\demo-runs\\provider-switch-live-20260622-224524\\workspace\nProvider Switch Live 20260622-224524",
    });

    expect(recentProjectDisplayName(project)).toBe("Provider Switch Live 20260622-224524");
  });

  it("keeps full path details in the hover payload", () => {
    const project = buildProject();

    expect(recentProjectHoverDetail(project)).toBe(
      "D:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace\nD:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/demo.abproj",
    );
  });

  it("uses the full path only inside the tooltip payload", () => {
    const project = buildProject();

    expect(recentProjectTooltip(project)).toBe(
      "Provider Switch Live 20260622-224524\nD:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/workspace\nD:/AstraBridge/PRIVATE/demo-runs/provider-switch-live-20260622-224524/demo.abproj",
    );
  });

  it("keeps only a short workspace tail for the visible secondary label", () => {
    const project = buildProject();

    expect(recentProjectCompactLocation(project)).toBe("provider-switch-live-20260622-224524/workspace");
  });

  it("falls back to the project file tail when the workspace path is missing", () => {
    const project = buildProject({ workspace_root: "" });

    expect(recentProjectCompactLocation(project)).toBe("provider-switch-live-20260622-224524/demo.abproj");
  });
});
