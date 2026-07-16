import { create } from "zustand";
import type {
  AppearancePreset,
  CursorEnhancementPreference,
  EventSnapshot,
  LocaleCode,
  PermissionMode,
  ProjectFile,
  RuntimeActivityState,
  RuntimeDiffSummary,
  ShellThreadSettings,
} from "./types";

import { normalizeCursorEnhancementPreference } from "./features/brand/cursorEnhancement";

type AppState = {
  project: ProjectFile | null;
  locale: LocaleCode;
  appearance: AppearancePreset;
  cursorEnhancement: CursorEnhancementPreference;
  leftSidebarOpen: boolean;
  leftSidebarWidth: number;
  rightSidebarWidth: number;
  rightSidebarOpen: boolean;
  commandPaletteOpen: boolean;
  eventCursor: number;
  eventSnapshot: EventSnapshot;
  setProject: (project: ProjectFile | null) => void;
  setLocale: (locale: LocaleCode) => void;
  setAppearance: (appearance: AppearancePreset) => void;
  setCursorEnhancement: (preference: CursorEnhancementPreference) => void;
  setLeftSidebarWidth: (width: number) => void;
  setRightSidebarWidth: (width: number) => void;
  toggleLeftSidebar: () => void;
  toggleRightSidebar: () => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setEventCursor: (cursor: number) => void;
  applyAgentDelta: (threadId: string, turnId: string, delta: string) => void;
  applyPlanDelta: (threadId: string, turnId: string, delta: string) => void;
  appendReasoningDelta: (threadId: string, turnId: string, delta: string, source: string, label?: string) => void;
  setTurnActivity: (threadId: string, turnId: string, activity: RuntimeActivityState) => void;
  setTurnDiff: (threadId: string, turnId: string, diff: RuntimeDiffSummary) => void;
  setPlan: (threadId: string, turnId: string, explanation: string | null, plan: EventSnapshot["planByThread"][string]["plan"]) => void;
  setTokenUsage: (threadId: string, turnId: string, tokenUsage: EventSnapshot["tokenUsageByThread"][string]) => void;
  setThreadStatus: (threadId: string, status: EventSnapshot["threadStatusByThread"][string]) => void;
  clearLiveTurn: (threadId: string, turnId: string) => void;
  threadSettingsDraft: Record<string, ShellThreadSettings>;
  setThreadSettingsDraft: (threadId: string, patch: Partial<ShellThreadSettings>) => void;
};

const EMPTY_EVENTS: EventSnapshot = {
  liveTextByTurn: {},
  livePlanTextByTurn: {},
  liveReasoningByTurn: {},
  activityByTurn: {},
  diffByTurn: {},
  planByThread: {},
  tokenUsageByThread: {},
  latestTurnIdByThread: {},
  threadStatusByThread: {},
};

const CURSOR_ENHANCEMENT_STORAGE_KEY = "astrabridge.cursorEnhancement";

function readCursorEnhancementPreference(): CursorEnhancementPreference {
  if (typeof window === "undefined") {
    return "auto";
  }
  return normalizeCursorEnhancementPreference(window.localStorage.getItem(CURSOR_ENHANCEMENT_STORAGE_KEY));
}

function persistCursorEnhancementPreference(preference: CursorEnhancementPreference) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(CURSOR_ENHANCEMENT_STORAGE_KEY, preference);
}

export const useAppStore = create<AppState>((set) => ({
  project: null,
  locale: "zh-CN",
  appearance: "codex",
  cursorEnhancement: readCursorEnhancementPreference(),
  leftSidebarOpen: true,
  leftSidebarWidth: 300,
  rightSidebarWidth: 340,
  rightSidebarOpen: true,
  commandPaletteOpen: false,
  eventCursor: 0,
  eventSnapshot: EMPTY_EVENTS,
  threadSettingsDraft: {},
  setProject: (project) =>
    set(() => ({
      project,
      locale: project?.ui_preferences.locale ?? "zh-CN",
      appearance: project?.ui_preferences.appearance ?? "codex",
      cursorEnhancement: normalizeCursorEnhancementPreference(project?.ui_preferences.cursor_enhancement ?? readCursorEnhancementPreference()),
      leftSidebarOpen: project?.ui_preferences.left_sidebar_open ?? true,
      leftSidebarWidth: project?.ui_preferences.left_sidebar_width ?? 300,
      rightSidebarWidth: project?.ui_preferences.right_sidebar_width ?? 340,
      rightSidebarOpen: project?.ui_preferences.right_sidebar_open ?? true,
      eventCursor: 0,
      eventSnapshot: EMPTY_EVENTS,
      threadSettingsDraft: {},
    })),
  setLocale: (locale) => set(() => ({ locale })),
  setAppearance: (appearance) => set(() => ({ appearance })),
  setCursorEnhancement: (cursorEnhancement) => {
    persistCursorEnhancementPreference(cursorEnhancement);
    set(() => ({ cursorEnhancement }));
  },
  setLeftSidebarWidth: (width) =>
    set(() => {
      const viewportWidth = typeof window === "undefined" ? 1280 : window.innerWidth;
      return { leftSidebarWidth: Math.max(220, Math.min(width, Math.min(520, viewportWidth - 420))) };
    }),
  setRightSidebarWidth: (width) =>
    set(() => {
      const viewportWidth = typeof window === "undefined" ? 1280 : window.innerWidth;
      return { rightSidebarWidth: Math.max(280, Math.min(width, Math.max(520, viewportWidth - 360))) };
    }),
  toggleLeftSidebar: () => set((state) => ({ leftSidebarOpen: !state.leftSidebarOpen })),
  toggleRightSidebar: () => set((state) => ({ rightSidebarOpen: !state.rightSidebarOpen })),
  setCommandPaletteOpen: (open) => set(() => ({ commandPaletteOpen: open })),
  setEventCursor: (cursor) => set(() => ({ eventCursor: cursor })),
  applyAgentDelta: (threadId, turnId, delta) =>
    set((state) => ({
      eventSnapshot: {
        ...state.eventSnapshot,
        liveTextByTurn: {
          ...state.eventSnapshot.liveTextByTurn,
          [turnId]: (state.eventSnapshot.liveTextByTurn[turnId] ?? "") + delta,
        },
        latestTurnIdByThread: {
          ...state.eventSnapshot.latestTurnIdByThread,
          [threadId]: turnId,
        },
      },
    })),
  applyPlanDelta: (threadId, turnId, delta) =>
    set((state) => ({
      eventSnapshot: {
        ...state.eventSnapshot,
        livePlanTextByTurn: {
          ...state.eventSnapshot.livePlanTextByTurn,
          [turnId]: (state.eventSnapshot.livePlanTextByTurn[turnId] ?? "") + delta,
        },
        latestTurnIdByThread: {
          ...state.eventSnapshot.latestTurnIdByThread,
          [threadId]: turnId,
        },
      },
    })),
  appendReasoningDelta: (threadId, turnId, delta, source, label = "provider reasoning") =>
    set((state) => {
      const previous = state.eventSnapshot.liveReasoningByTurn[turnId];
      return {
        eventSnapshot: {
          ...state.eventSnapshot,
          liveReasoningByTurn: {
            ...state.eventSnapshot.liveReasoningByTurn,
            [turnId]: {
              text: `${previous?.text ?? ""}${delta}`,
              source,
              label,
            },
          },
          activityByTurn: {
            ...state.eventSnapshot.activityByTurn,
            [turnId]: {
              kind: "thinking",
              label: "正在思考",
              status: "active",
              preview: delta.trim() || previous?.text?.trim() || "Receiving provider reasoning",
              updated_at: new Date().toISOString(),
            },
          },
          latestTurnIdByThread: {
            ...state.eventSnapshot.latestTurnIdByThread,
            [threadId]: turnId,
          },
        },
      };
    }),
  setTurnActivity: (threadId, turnId, activity) =>
    set((state) => {
      const previous = state.eventSnapshot.activityByTurn[turnId];
      const sameItem = previous && previous.item_id && previous.item_id === activity.item_id;
      const sameKind = previous && previous.kind === activity.kind;
      const shouldAppendDetail = Boolean(activity.detail && sameKind && (sameItem || !activity.item_id));
      const detail = shouldAppendDetail
        ? [previous?.detail, activity.detail].filter(Boolean).join("\n")
        : activity.detail ?? previous?.detail;
      const preview =
        activity.preview ||
        previous?.preview ||
        (activity.detail ? activity.detail.split(/\r?\n/).find((line) => line.trim()) : undefined);
      return {
        eventSnapshot: {
          ...state.eventSnapshot,
          activityByTurn: {
            ...state.eventSnapshot.activityByTurn,
            [turnId]: {
              ...activity,
              preview,
              detail,
              updated_at: activity.updated_at ?? new Date().toISOString(),
            },
          },
          latestTurnIdByThread: {
            ...state.eventSnapshot.latestTurnIdByThread,
            [threadId]: turnId,
          },
        },
      };
    }),
  setTurnDiff: (threadId, turnId, diff) =>
    set((state) => ({
      eventSnapshot: {
        ...state.eventSnapshot,
        diffByTurn: {
          ...state.eventSnapshot.diffByTurn,
          [turnId]: {
            ...diff,
            updated_at: diff.updated_at ?? new Date().toISOString(),
          },
        },
        activityByTurn: {
          ...state.eventSnapshot.activityByTurn,
          [turnId]: {
            kind: "file_change",
            label: "正在修改文件",
            status: "active",
            preview:
              diff.file_paths && diff.file_paths.length > 0
                ? `${diff.file_paths.slice(0, 2).join(", ")}${diff.file_paths.length > 2 ? ` +${diff.file_paths.length - 2} more` : ""}`
                : `${diff.files} files, +${diff.added} -${diff.deleted}`,
            detail:
              diff.detail ||
              [
                diff.file_paths?.length ? diff.file_paths.join("\n") : "",
                `files: ${diff.files}`,
                `added: ${diff.added}`,
                `deleted: ${diff.deleted}`,
              ]
                .filter(Boolean)
                .join("\n"),
            updated_at: diff.updated_at ?? new Date().toISOString(),
          },
        },
        latestTurnIdByThread: {
          ...state.eventSnapshot.latestTurnIdByThread,
          [threadId]: turnId,
        },
      },
    })),
  setPlan: (threadId, turnId, explanation, plan) =>
    set((state) => ({
      eventSnapshot: {
        ...state.eventSnapshot,
        planByThread: {
          ...state.eventSnapshot.planByThread,
          [threadId]: { explanation, plan },
        },
        latestTurnIdByThread: {
          ...state.eventSnapshot.latestTurnIdByThread,
          [threadId]: turnId,
        },
      },
    })),
  setTokenUsage: (threadId, turnId, tokenUsage) =>
    set((state) => ({
      eventSnapshot: {
        ...state.eventSnapshot,
        tokenUsageByThread: {
          ...state.eventSnapshot.tokenUsageByThread,
          [threadId]: tokenUsage,
        },
        latestTurnIdByThread: {
          ...state.eventSnapshot.latestTurnIdByThread,
          [threadId]: turnId,
        },
      },
    })),
  setThreadStatus: (threadId, status) =>
    set((state) => ({
      eventSnapshot: {
        ...state.eventSnapshot,
        threadStatusByThread: {
          ...state.eventSnapshot.threadStatusByThread,
          [threadId]: status,
        },
      },
    })),
  clearLiveTurn: (threadId, turnId) =>
    set((state) => {
      const liveTextByTurn = { ...state.eventSnapshot.liveTextByTurn };
      const livePlanTextByTurn = { ...state.eventSnapshot.livePlanTextByTurn };
      const liveReasoningByTurn = { ...state.eventSnapshot.liveReasoningByTurn };
      const activityByTurn = { ...state.eventSnapshot.activityByTurn };
      const diffByTurn = { ...state.eventSnapshot.diffByTurn };
      delete liveTextByTurn[turnId];
      delete livePlanTextByTurn[turnId];
      delete liveReasoningByTurn[turnId];
      delete activityByTurn[turnId];
      delete diffByTurn[turnId];
      const latestTurnIdByThread = { ...state.eventSnapshot.latestTurnIdByThread };
      if (latestTurnIdByThread[threadId] === turnId) {
        delete latestTurnIdByThread[threadId];
      }
      return {
        eventSnapshot: {
          ...state.eventSnapshot,
          liveTextByTurn,
          livePlanTextByTurn,
          liveReasoningByTurn,
          activityByTurn,
          diffByTurn,
          latestTurnIdByThread,
        },
      };
    }),
  setThreadSettingsDraft: (threadId, patch) =>
    set((state) => ({
      threadSettingsDraft: {
        ...state.threadSettingsDraft,
        [threadId]: {
          ...state.threadSettingsDraft[threadId],
          ...patch,
        },
      },
    })),
}));

export const PERMISSION_MODE_ORDER: PermissionMode[] = ["ask", "auto", "full"];

