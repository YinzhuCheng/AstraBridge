import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectTaskTree } from "./ProjectTaskTree";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function buildTask(
  index: number,
  patch: Partial<ComponentProps<typeof ProjectTaskTree>["projects"][number]["tasks"][number]> = {},
) {
  return {
    task_id: `task-${index}`,
    title: `Task ${index}`,
    status: "active",
    updated_at: "2026-06-27T01:00:00Z",
    is_current: index === 1,
    active_provider_thread_id: `thread-${index}`,
    provider_id: "qwen",
    model: "qwen3.7-plus",
    reasoning_effort: "high",
    thread_count: 1,
    lane_count: 1,
    active_lane_label: "qwen / qwen3.7-plus",
    previous_lane_label: "openai / gpt-5.5",
    latest_lane_status: "completed",
    handoff_count: 2,
    checkpoint_count: 1,
    missing_thread_count: 0,
    threads: [
      {
        thread_id: `thread-${index}`,
        title: "qwen / qwen3.7-plus",
        provider_id: "qwen",
        model: "qwen3.7-plus",
        reasoning_effort: "high",
        role: "provider",
        updated_at: "2026-06-27T01:10:00Z",
        is_active: true,
      },
    ],
    ...patch,
  };
}

function buildProps(patch: Partial<ComponentProps<typeof ProjectTaskTree>> = {}): ComponentProps<typeof ProjectTaskTree> {
  return {
    locale: "en",
    projects: [
      {
        project_id: "p1",
        name: "AstraBridge",
        project_file: "D:/AstraBridge/project.abproj",
        workspace_root: "D:/AstraBridge",
        updated_at: "2026-06-27T00:00:00Z",
        is_current: true,
        tasks: [
          buildTask(1, {
            title: "Current StarBridge Project",
            active_provider_thread_id: "thread-1",
            is_current: true,
          }),
        ],
      },
    ],
    expandedProjects: new Set(["D:/AstraBridge/project.abproj"]),
    formatTime: () => "5m",
    onToggleProject: vi.fn(),
    onSelectProject: vi.fn(),
    onSelectTask: vi.fn(),
    ...patch,
  };
}

describe("ProjectTaskTree", () => {
  it("renders only project and task rows with title and time", () => {
    render(<ProjectTaskTree {...buildProps()} />);

    const projectRow = screen.getByRole("button", { name: /AstraBridge/ });
    const taskRow = screen.getByRole("button", { name: /Current StarBridge Project/ });

    expect(within(projectRow).getByText("5m")).toBeInTheDocument();
    expect(within(taskRow).getByText("5m")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /qwen \/ qwen3\.7-plus/ })).not.toBeInTheDocument();
    expect(within(taskRow).queryByText("high")).not.toBeInTheDocument();
  });

  it("calls project toggle and task selection handlers without selecting lanes", () => {
    const onToggleProject = vi.fn();
    const onSelectTask = vi.fn();
    render(<ProjectTaskTree {...buildProps({ onToggleProject, onSelectTask })} />);

    fireEvent.click(screen.getByLabelText("Collapse project"));
    fireEvent.click(screen.getByRole("button", { name: /Current StarBridge Project/ }));

    expect(onToggleProject).toHaveBeenCalledWith("D:/AstraBridge/project.abproj");
    expect(onSelectTask).toHaveBeenCalledWith(expect.objectContaining({ name: "AstraBridge" }), expect.objectContaining({ task_id: "task-1" }));
  });

  it("lets an optimistic sidebar selection override the stale active highlight", () => {
    const tasks = [
      buildTask(1, { title: "Old task", is_current: true }),
      buildTask(2, { title: "New task", is_current: false }),
    ];
    render(
      <ProjectTaskTree
        {...buildProps({
          projects: [{ ...buildProps().projects[0], tasks }],
          selectedProjectKey: "D:/AstraBridge/project.abproj",
          selectedTaskId: "task-2",
        })}
      />,
    );

    const activeRows = Array.from(document.querySelectorAll(".project-tree-item-active .project-tree-row"));
    expect(activeRows).toHaveLength(1);
    expect(activeRows[0]).toHaveTextContent("New task");
  });

  it("keeps active and previous lane details in the task hover card", () => {
    render(<ProjectTaskTree {...buildProps()} />);

    expect(screen.getByText("Active lane")).toBeInTheDocument();
    expect(screen.getByText("qwen / qwen3.7-plus")).toBeInTheDocument();
    expect(screen.getByText("Previous lane")).toBeInTheDocument();
    expect(screen.getByText("openai / gpt-5.5")).toBeInTheDocument();
    expect(screen.getByText("Execution lanes")).toBeInTheDocument();
    expect(screen.getByText("Lane status")).toBeInTheDocument();
  });

  it("moves long project paths into the row tooltip", () => {
    render(<ProjectTaskTree {...buildProps()} />);

    const projectRow = screen.getByRole("button", { name: /AstraBridge/ });
    expect(projectRow).toHaveAttribute("title", "AstraBridge\nD:/AstraBridge\nD:/AstraBridge/project.abproj");
    expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
    expect(screen.queryByText("Project file")).not.toBeInTheDocument();
  });

  it("hides smoke-step prefixes from visible task titles", () => {
    render(
      <ProjectTaskTree
        {...buildProps({
          projects: [
            {
              ...buildProps().projects[0],
              tasks: [
                buildTask(1, {
                  title: "Step 11 source for compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run",
                  is_current: true,
                }),
              ],
            },
          ],
        })}
      />,
    );

    const taskRow = screen.getByRole("button", { name: /compact_handoff-yunwu-gpt-5\.5-same_task\.handoff_target-run/i });
    expect(taskRow).toBeInTheDocument();
    expect(taskRow).not.toHaveTextContent(/Step 11 source for/i);
    expect(taskRow).toHaveAttribute("title", "compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run");
    const taskTooltip = screen.getAllByRole("tooltip").find((item) =>
      item.textContent?.includes("compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run"),
    );
    expect(taskTooltip).toBeTruthy();
    expect(taskTooltip).toHaveTextContent("compact_handoff-yunwu-gpt-5.5-same_task.handoff_target-run");
    expect(taskTooltip).not.toHaveTextContent(/Step 11 source for/i);
  });

  it("strongly highlights the current task instead of both project and task", () => {
    render(<ProjectTaskTree {...buildProps()} />);

    const activeRows = document.querySelectorAll(".project-tree-item-active");
    expect(activeRows).toHaveLength(1);
    expect(activeRows[0]).toHaveTextContent("Current StarBridge Project");
  });

  it("keeps collapsed projects compact without rendering task children", () => {
    render(<ProjectTaskTree {...buildProps({ expandedProjects: new Set() })} />);

    expect(screen.getByRole("treeitem", { expanded: false })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AstraBridge/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Current StarBridge Project/ })).not.toBeInTheDocument();
    expect(document.querySelector(".project-tree-children")).not.toBeInTheDocument();
  });

  it("shows at most five tasks per project until expanded", () => {
    const baseProject = buildProps().projects[0];
    render(
      <ProjectTaskTree
        {...buildProps({
          projects: [
            {
              ...baseProject,
              tasks: Array.from({ length: 7 }, (_, index) => buildTask(index + 1)),
            },
          ],
        })}
      />,
    );

    expect(screen.getByRole("button", { name: /Task 1/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Task 5/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Task 6/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show 2 more" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show 2 more" }));

    expect(screen.getByRole("button", { name: /Task 6/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Task 7/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Collapse" })).toBeInTheDocument();
  });

  it("renders tasks inside an indented child list", () => {
    render(<ProjectTaskTree {...buildProps()} />);

    expect(document.querySelector(".project-tree-children-list .project-tree-child-group")).toBeInTheDocument();
  });
});
