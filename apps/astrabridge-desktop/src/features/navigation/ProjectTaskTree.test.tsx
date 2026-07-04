import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectTaskTree } from "./ProjectTaskTree";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function buildProps(patch: Partial<ComponentProps<typeof ProjectTaskTree>> = {}): ComponentProps<typeof ProjectTaskTree> {
  return {
    locale: "zh-CN",
    projects: [
      {
        project_id: "p1",
        name: "AstraBridge",
        project_file: "D:/AstraBridge/project.abproj",
        workspace_root: "D:/AstraBridge",
        updated_at: "2026-06-27T00:00:00Z",
        is_current: true,
        tasks: [
          {
            task_id: "task-1",
            title: "调研接口成本",
            status: "active",
            updated_at: "2026-06-27T01:00:00Z",
            is_current: true,
            active_provider_thread_id: "thread-1",
            provider_id: "qwen",
            model: "qwen3.7-plus",
            reasoning_effort: "high",
            thread_count: 1,
            lane_count: 1,
            active_lane_label: "qwen / qwen3.7-plus",
            latest_lane_status: "completed",
            handoff_count: 2,
            checkpoint_count: 1,
            missing_thread_count: 0,
            threads: [
              {
                thread_id: "thread-1",
                title: "qwen / qwen3.7-plus",
                provider_id: "qwen",
                model: "qwen3.7-plus",
                reasoning_effort: "high",
                role: "provider",
                updated_at: "2026-06-27T01:10:00Z",
                is_active: true,
              },
            ],
          },
        ],
      },
    ],
    expandedProjects: new Set(["D:/AstraBridge/project.abproj"]),
    formatTime: () => "5 分钟",
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
    const taskRow = screen.getByRole("button", { name: /调研接口成本/ });

    expect(within(projectRow).getByText("5 分钟")).toBeInTheDocument();
    expect(within(taskRow).getByText("5 分钟")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /qwen \/ qwen3\.7-plus/ })).not.toBeInTheDocument();
    expect(within(taskRow).queryByText("high")).not.toBeInTheDocument();
  });

  it("calls project toggle and task selection handlers without selecting lanes", () => {
    const onToggleProject = vi.fn();
    const onSelectTask = vi.fn();
    render(<ProjectTaskTree {...buildProps({ onToggleProject, onSelectTask })} />);

    fireEvent.click(screen.getByLabelText("收起项目"));
    fireEvent.click(screen.getByRole("button", { name: /调研接口成本/ }));

    expect(onToggleProject).toHaveBeenCalledWith("D:/AstraBridge/project.abproj");
    expect(onSelectTask).toHaveBeenCalledWith(expect.objectContaining({ name: "AstraBridge" }), expect.objectContaining({ task_id: "task-1" }));
  });

  it("keeps lane details in the task hover card", () => {
    render(<ProjectTaskTree {...buildProps()} />);

    expect(screen.getByText("工作区")).toBeInTheDocument();
    expect(screen.getByText("D:/AstraBridge")).toBeInTheDocument();
    expect(screen.getByText("活动线路")).toBeInTheDocument();
    expect(screen.getByText("qwen / qwen3.7-plus")).toBeInTheDocument();
    expect(screen.getByText("执行线路")).toBeInTheDocument();
    expect(screen.getByText("线路状态")).toBeInTheDocument();
  });

  it("strongly highlights the current task instead of both project and task", () => {
    render(<ProjectTaskTree {...buildProps()} />);

    const activeRows = document.querySelectorAll(".project-tree-item-active");
    expect(activeRows).toHaveLength(1);
    expect(activeRows[0]).toHaveTextContent("调研接口成本");
  });

  it("keeps collapsed projects compact without rendering task children", () => {
    render(<ProjectTaskTree {...buildProps({ expandedProjects: new Set() })} />);

    expect(screen.getByRole("treeitem", { expanded: false })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AstraBridge/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /调研接口成本/ })).not.toBeInTheDocument();
    expect(document.querySelector(".project-tree-children")).not.toBeInTheDocument();
  });
});
