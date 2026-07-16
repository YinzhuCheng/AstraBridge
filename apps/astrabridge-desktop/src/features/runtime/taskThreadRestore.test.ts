import { describe, expect, it } from "vitest";

import type { ProjectFile, ProjectTask, ProjectTasksResponse, ShellThread } from "../../types";
import {
  fallbackThreadIdForEmptyTaskContext,
  resolveCurrentProjectTask,
  resolveSelectedThreadProfileId,
  resolveTaskIdForNewThread,
  resolveTaskSendTargetThreadId,
  resolveVisibleCurrentProjectTask,
  shouldUseSelectedRuntimeThread,
} from "./taskThreadRestore";

function buildProject(overrides: Partial<ProjectFile> = {}): ProjectFile {
  return {
    schema_version: "astrabridge-project-v1",
    project_id: "project-1",
    name: "Project",
    project_file: "D:/AstraBridge/demo.abproj",
    workspace_root: "D:/AstraBridge",
    entry_mode: "existing",
    default_profile_id: "profile-default",
    default_model: "qwen3-coder-plus",
    default_effort: "medium",
    current_thread_id: "thread-1",
    current_task_id: "task-1",
    recent_threads: ["thread-1"],
    recent_tasks: ["task-1"],
    ui_preferences: {},
    created_at: "2026-07-07T00:00:00Z",
    updated_at: "2026-07-07T00:00:00Z",
    ...overrides,
  };
}

function buildTask(overrides: Partial<ProjectTask> = {}): ProjectTask {
  return {
    schema_version: "astrabridge-project-task-v1",
    task_id: "task-1",
    title: "Task 1",
    status: "active",
    handoff_policy: "multi_provider_handoff",
    active_provider_thread_id: "thread-1",
    provider_threads: [],
    handoff_events: [],
    created_at: "2026-07-07T00:00:00Z",
    updated_at: "2026-07-07T00:00:00Z",
    ...overrides,
  };
}

function buildProjectTasksResponse(overrides: Partial<ProjectTasksResponse> = {}): ProjectTasksResponse {
  return {
    schema_version: "astrabridge-project-tasks-v1",
    current_task: null,
    tasks: [],
    updated_at: "2026-07-07T00:00:00Z",
    ...overrides,
  };
}

function buildThreadSummary(overrides: Partial<Pick<ShellThread, "shellSettings">> = {}): Pick<ShellThread, "shellSettings"> {
  return {
    shellSettings: {},
    ...overrides,
  };
}

describe("resolveCurrentProjectTask", () => {
  it("falls back to the persisted current_task_id when current_task is temporarily missing", () => {
    const restoredTask = buildTask({ task_id: "task-1", title: "Reloaded task" });
    const project = buildProject({ current_task_id: "task-1" });
    const projectTasks = buildProjectTasksResponse({
      current_task: null,
      tasks: [restoredTask, buildTask({ task_id: "task-2", title: "Older task" })],
    });

    expect(resolveCurrentProjectTask(project, projectTasks)?.title).toBe("Reloaded task");
  });

  it("uses the explicit current_task payload when the project has no current-task pointer", () => {
    const currentTask = buildTask({ task_id: "task-9", title: "Current task" });
    const projectTasks = buildProjectTasksResponse({
      current_task: currentTask,
      tasks: [buildTask({ task_id: "task-1", title: "Cached task" })],
    });

    expect(resolveCurrentProjectTask(buildProject({ current_task_id: null }), projectTasks)?.task_id).toBe("task-9");
  });

  it("does not route a newly selected task through a stale current_task response", () => {
    const selectedTask = buildTask({ task_id: "task-new", title: "Fresh task", active_provider_thread_id: "thread-new" });
    const staleTask = buildTask({ task_id: "task-old", title: "Stale task", active_provider_thread_id: "thread-old" });
    const projectTasks = buildProjectTasksResponse({
      current_task: staleTask,
      tasks: [selectedTask, staleTask],
    });

    expect(resolveCurrentProjectTask(buildProject({ current_task_id: "task-new" }), projectTasks)?.task_id).toBe("task-new");
  });
});

describe("resolveVisibleCurrentProjectTask", () => {
  it("prefers the reconciled current task when a pending sidebar placeholder points at the same task", () => {
    const pendingSidebarTask = buildTask({
      task_id: "task-graph",
      title: "DG Graph Parallel 01 Fresh",
      graph_definitions: [],
      graph_run_refs: [],
      graph_snapshot_refs: [],
    });
    const resolvedCurrentTask = buildTask({
      task_id: "task-graph",
      title: "DG Graph Parallel 01 Fresh",
      graph_definitions: [{ graph_id: "graph-1", nodes: [], edges: [] }] as unknown as ProjectTask["graph_definitions"],
      graph_run_refs: [{ run_id: "run-1" }] as unknown as ProjectTask["graph_run_refs"],
      graph_snapshot_refs: [{ snapshot_id: "snapshot-1" }] as unknown as ProjectTask["graph_snapshot_refs"],
    });

    const visible = resolveVisibleCurrentProjectTask({
      pendingSidebarTask,
      taskSelectionGuard: null,
      resolvedCurrentTask,
    });

    expect(visible?.graph_definitions).toHaveLength(1);
    expect(visible?.graph_run_refs).toHaveLength(1);
    expect(visible?.graph_snapshot_refs).toHaveLength(1);
  });

  it("keeps the optimistic task while the reconciled task still points at a different task id", () => {
    const optimisticTask = buildTask({ task_id: "task-new", title: "Fresh task" });
    const resolvedCurrentTask = buildTask({ task_id: "task-old", title: "Old task" });

    const visible = resolveVisibleCurrentProjectTask({
      pendingSidebarTask: null,
      taskSelectionGuard: optimisticTask,
      resolvedCurrentTask,
    });

    expect(visible?.task_id).toBe("task-new");
  });
});

describe("resolveSelectedThreadProfileId", () => {
  it("falls back to the project default profile during reload when the thread id is known", () => {
    const value = resolveSelectedThreadProfileId({
      currentTask: buildTask({ provider_threads: [] }),
      selectedThreadId: "thread-1",
      threadSettingsProfileId: null,
      selectedThreadSummary: buildThreadSummary({ shellSettings: {} }),
      projectDefaultProfileId: "profile-default",
      listProfileId: "profile-list",
    });

    expect(value).toBe("profile-default");
  });

  it("prefers the provider-thread profile when the restored task already knows it", () => {
    const value = resolveSelectedThreadProfileId({
      currentTask: buildTask({
        provider_threads: [{ thread_id: "thread-1", profile_id: "profile-provider" }],
      }),
      selectedThreadId: "thread-1",
      threadSettingsProfileId: "profile-draft",
      selectedThreadSummary: buildThreadSummary({ shellSettings: { profile_id: "profile-summary" } }),
      projectDefaultProfileId: "profile-default",
      listProfileId: "profile-list",
    });

    expect(value).toBe("profile-provider");
  });

  it("does not crash when a temporarily compact task omits provider_threads", () => {
    const value = resolveSelectedThreadProfileId({
      currentTask: { ...buildTask(), provider_threads: undefined as unknown as ProjectTask["provider_threads"] },
      selectedThreadId: "thread-1",
      threadSettingsProfileId: null,
      selectedThreadSummary: buildThreadSummary({ shellSettings: {} }),
      projectDefaultProfileId: "profile-default",
      listProfileId: "profile-list",
    });

    expect(value).toBe("profile-default");
  });
});

describe("resolveTaskSendTargetThreadId", () => {
  it("does not reuse a stale selected thread when the current task has no active provider lane", () => {
    const value = resolveTaskSendTargetThreadId({
      currentTask: {
        ...buildTask(),
        active_provider_thread_id: null,
        provider_threads: [],
      },
      selectedThreadId: "thread-stale",
    });

    expect(value).toBeNull();
  });

  it("keeps the selected thread when it still belongs to the current task", () => {
    const value = resolveTaskSendTargetThreadId({
      currentTask: buildTask({
        active_provider_thread_id: null,
        provider_threads: [{ thread_id: "thread-b", profile_id: "profile-provider" }],
      }),
      selectedThreadId: "thread-b",
    });

    expect(value).toBe("thread-b");
  });

  it("prefers the current task active provider thread", () => {
    const value = resolveTaskSendTargetThreadId({
      currentTask: buildTask({
        active_provider_thread_id: "thread-active",
        provider_threads: [{ thread_id: "thread-active", profile_id: "profile-provider" }],
      }),
      selectedThreadId: "thread-stale",
    });

    expect(value).toBe("thread-active");
  });
});

describe("resolveTaskIdForNewThread", () => {
  it("keeps a new lane on the task explicitly selected by the user during a project-pointer race", () => {
    expect(
      resolveTaskIdForNewThread({
        selectedTaskId: "task-selected",
        conversationTaskId: "task-selected",
        currentTask: buildTask({ task_id: "task-stale" }),
      }),
    ).toBe("task-selected");
  });

  it("falls back to the current task when the conversation has not loaded yet", () => {
    expect(resolveTaskIdForNewThread({ selectedTaskId: null, conversationTaskId: null, currentTask: buildTask({ task_id: "task-current" }) })).toBe("task-current");
  });
});

describe("shouldUseSelectedRuntimeThread", () => {
  it("rejects a stale runtime thread when the current task has no lane", () => {
    const value = shouldUseSelectedRuntimeThread({
      currentTask: buildTask({
        active_provider_thread_id: null,
        provider_threads: [],
      }),
      selectedThreadId: "thread-stale",
    });

    expect(value).toBe(false);
  });

  it("accepts the active provider thread for the current task", () => {
    const value = shouldUseSelectedRuntimeThread({
      currentTask: buildTask({
        active_provider_thread_id: "thread-active",
        provider_threads: [{ thread_id: "thread-active", profile_id: "profile-provider" }],
      }),
      selectedThreadId: "thread-active",
    });

    expect(value).toBe(true);
  });

  it("accepts the selected runtime thread when no task is currently scoped", () => {
    const value = shouldUseSelectedRuntimeThread({
      currentTask: null,
      selectedThreadId: "thread-free",
    });

    expect(value).toBe(true);
  });
});

describe("fallbackThreadIdForEmptyTaskContext", () => {
  it("does not auto-fallback to the first thread when the current task has no lane yet", () => {
    const value = fallbackThreadIdForEmptyTaskContext({
      currentTask: buildTask({ active_provider_thread_id: null, provider_threads: [] }),
      selectedThreadId: null,
      threads: [{ id: "thread-old" }],
    });

    expect(value).toBeNull();
  });

  it("falls back to the first thread only when there is no current task at all", () => {
    const value = fallbackThreadIdForEmptyTaskContext({
      currentTask: null,
      selectedThreadId: null,
      threads: [{ id: "thread-old" }],
    });

    expect(value).toBe("thread-old");
  });
});
