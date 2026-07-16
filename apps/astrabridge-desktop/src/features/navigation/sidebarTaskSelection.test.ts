import { describe, expect, it } from "vitest";

import { isSidebarTaskAlreadySelected } from "./sidebarTaskSelection";

describe("isSidebarTaskAlreadySelected", () => {
  it("returns true for the current task inside the current project", () => {
    expect(
      isSidebarTaskAlreadySelected({
        currentProject: {
          project_file: "D:/AstraBridge/project.abproj",
          project_id: "project-1",
        },
        currentTask: {
          task_id: "task-1",
        },
        projectNode: {
          is_current: false,
          project_file: "D:/AstraBridge/project.abproj",
          project_id: "project-1",
        },
        taskNode: {
          task_id: "task-1",
        },
      }),
    ).toBe(true);
  });

  it("returns true when the sidebar project is already marked current", () => {
    expect(
      isSidebarTaskAlreadySelected({
        currentProject: {
          project_file: "D:/AstraBridge/project.abproj",
          project_id: "project-1",
        },
        currentTask: {
          task_id: "task-1",
        },
        projectNode: {
          is_current: true,
          project_file: "D:/AstraBridge/other.abproj",
          project_id: "project-2",
        },
        taskNode: {
          task_id: "task-1",
        },
      }),
    ).toBe(true);
  });

  it("returns false when the task matches but the project does not", () => {
    expect(
      isSidebarTaskAlreadySelected({
        currentProject: {
          project_file: "D:/AstraBridge/project.abproj",
          project_id: "project-1",
        },
        currentTask: {
          task_id: "task-1",
        },
        projectNode: {
          is_current: false,
          project_file: "D:/AstraBridge/other.abproj",
          project_id: "project-2",
        },
        taskNode: {
          task_id: "task-1",
        },
      }),
    ).toBe(false);
  });
});
