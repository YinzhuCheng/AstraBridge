import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

import type { TaskGraphTemplateSummary } from "../../types";
import {
  buildPendingRunInspectorStorageKey,
  consumePendingRunInspectorReopen,
  DEFAULT_TASK_GRAPH_SIDEBAR_WIDTH,
  normalizeTaskGraphPanelWidth,
  readStoredTaskGraphPanelWidth,
  readStoredTaskGraphWorkspaceState,
  TASK_GRAPH_SIDEBAR_WIDTH_STORAGE_KEY,
  taskGraphWorkspaceStateStorageKey,
  type TaskGraphWorkspaceStoredState,
  writePendingRunInspectorReopen,
  writeStoredTaskGraphPanelWidth,
  writeStoredTaskGraphWorkspaceState,
} from "./taskGraphWorkspacePersistence";

export type TaskGraphWorkspacePanelResizeState = {
  side: "left";
  startX: number;
  startWidth: number;
};

type UseTaskGraphWorkspaceChromeStateArgs = {
  taskId: string | null | undefined;
  graphId: string | null | undefined;
  graphTemplateId: string | null | undefined;
  templates: TaskGraphTemplateSummary[];
  dryRunBlocked: boolean;
  latestRunStatus: string | null | undefined;
  hasLatestRunRecovery: boolean;
  onInstantiateTemplate: (templateId: string) => void;
};

export function useTaskGraphWorkspaceChromeState({
  taskId,
  graphId,
  graphTemplateId,
  templates,
  dryRunBlocked,
  latestRunStatus,
  hasLatestRunRecovery,
  onInstantiateTemplate,
}: UseTaskGraphWorkspaceChromeStateArgs) {
  const modalReturnFocusRef = useRef<HTMLElement | null>(null);
  const normalizedTaskId = taskId ?? undefined;
  const normalizedGraphId = graphId ?? undefined;
  const initialWorkspaceStateKey = taskGraphWorkspaceStateStorageKey(
    normalizedTaskId,
    normalizedGraphId,
  );
  const initialPendingRunInspectorStorageKey =
    buildPendingRunInspectorStorageKey(initialWorkspaceStateKey);
  const initialPendingRunInspectorReopen = consumePendingRunInspectorReopen(
    initialPendingRunInspectorStorageKey,
  );
  const initialWorkspaceState = initialWorkspaceStateKey
    ? readStoredTaskGraphWorkspaceState(initialWorkspaceStateKey)
    : null;
  const [readinessExpanded, setReadinessExpanded] = useState(
    Boolean(initialWorkspaceState?.readinessExpanded),
  );
  const [latestRunExpanded, setLatestRunExpanded] = useState(
    Boolean(initialWorkspaceState?.latestRunExpanded),
  );
  const [recoveryExpanded, setRecoveryExpanded] = useState(
    Boolean(initialWorkspaceState?.recoveryExpanded),
  );
  const [inspectorWorkspace, setInspectorWorkspace] = useState<
    "selection" | "run"
  >(
    initialPendingRunInspectorReopen
      ? "run"
      : initialWorkspaceState?.inspectorWorkspace ?? "selection",
  );
  const [selectionInspectorRequested, setSelectionInspectorRequested] =
    useState(false);
  const [runInspectorRequested, setRunInspectorRequested] = useState(
    initialPendingRunInspectorReopen,
  );
  const [sidebarExpanded, setSidebarExpanded] = useState(
    Boolean(initialWorkspaceState?.sidebarExpanded),
  );
  const [inspectorExpanded, setInspectorExpanded] = useState(
    initialPendingRunInspectorReopen
      ? true
      : Boolean(initialWorkspaceState?.inspectorExpanded),
  );
  const [panelResizeState, setPanelResizeState] =
    useState<TaskGraphWorkspacePanelResizeState | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(() =>
    readStoredTaskGraphPanelWidth(
      "left",
      TASK_GRAPH_SIDEBAR_WIDTH_STORAGE_KEY,
      DEFAULT_TASK_GRAPH_SIDEBAR_WIDTH,
    ),
  );
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    templates[0]?.template_id ?? null,
  );
  const [templateBrowserOpen, setTemplateBrowserOpen] = useState(false);
  const selectedTemplateIdRef = useRef<string | null>(
    templates[0]?.template_id ?? null,
  );
  const workspaceStateStorageKey = useMemo(
    () => taskGraphWorkspaceStateStorageKey(normalizedTaskId, normalizedGraphId),
    [normalizedGraphId, normalizedTaskId],
  );
  const pendingRunInspectorStorageKey = useMemo(
    () => buildPendingRunInspectorStorageKey(workspaceStateStorageKey),
    [workspaceStateStorageKey],
  );
  const workspaceStateKeyRef = useRef<string | null>(initialWorkspaceStateKey);
  const [workspaceStateReady, setWorkspaceStateReady] = useState(true);

  useEffect(() => {
    selectedTemplateIdRef.current = selectedTemplateId;
  }, [selectedTemplateId]);

  useEffect(() => {
    if (!templates.length) {
      setSelectedTemplateId(null);
      selectedTemplateIdRef.current = null;
      return;
    }
    if (
      !selectedTemplateId ||
      !templates.some((template) => template.template_id === selectedTemplateId)
    ) {
      if (
        graphTemplateId &&
        templates.some((template) => template.template_id === graphTemplateId)
      ) {
        selectedTemplateIdRef.current = graphTemplateId;
        setSelectedTemplateId(graphTemplateId);
        return;
      }
      selectedTemplateIdRef.current = templates[0].template_id;
      setSelectedTemplateId(templates[0].template_id);
    }
  }, [graphTemplateId, selectedTemplateId, templates]);

  useEffect(() => {
    if (dryRunBlocked) {
      setReadinessExpanded(true);
    }
  }, [dryRunBlocked]);

  useEffect(() => {
    if (latestRunStatus === "running" || latestRunStatus === "paused_for_review") {
      setLatestRunExpanded(true);
      setInspectorWorkspace("run");
    }
  }, [latestRunStatus]);

  useEffect(() => {
    if (!hasLatestRunRecovery) return;
    setRecoveryExpanded(true);
    setLatestRunExpanded(true);
    setInspectorWorkspace("run");
  }, [hasLatestRunRecovery]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const handleWindowResize = () => {
      setSidebarWidth((current) =>
        normalizeTaskGraphPanelWidth("left", current),
      );
    };
    window.addEventListener("resize", handleWindowResize);
    return () => window.removeEventListener("resize", handleWindowResize);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    writeStoredTaskGraphPanelWidth(
      TASK_GRAPH_SIDEBAR_WIDTH_STORAGE_KEY,
      "left",
      sidebarWidth,
    );
  }, [sidebarWidth]);

  useEffect(() => {
    if (workspaceStateKeyRef.current === workspaceStateStorageKey) {
      return;
    }
    workspaceStateKeyRef.current = workspaceStateStorageKey;
    setWorkspaceStateReady(false);
    if (!workspaceStateStorageKey) {
      setSidebarExpanded(false);
      setInspectorExpanded(false);
      setInspectorWorkspace("selection");
      setRunInspectorRequested(false);
      setReadinessExpanded(false);
      setLatestRunExpanded(false);
      setRecoveryExpanded(false);
      setWorkspaceStateReady(true);
      return;
    }
    const storedState = readStoredTaskGraphWorkspaceState(
      workspaceStateStorageKey,
    );
    const pendingRunInspectorReopen = consumePendingRunInspectorReopen(
      pendingRunInspectorStorageKey,
    );
    setSidebarExpanded(Boolean(storedState?.sidebarExpanded));
    setInspectorExpanded(pendingRunInspectorReopen);
    setRunInspectorRequested(pendingRunInspectorReopen);
    setInspectorWorkspace(
      pendingRunInspectorReopen
        ? "run"
        : storedState?.inspectorWorkspace ?? "selection",
    );
    setReadinessExpanded(Boolean(storedState?.readinessExpanded));
    setLatestRunExpanded(Boolean(storedState?.latestRunExpanded));
    setRecoveryExpanded(Boolean(storedState?.recoveryExpanded));
    setWorkspaceStateReady(true);
  }, [pendingRunInspectorStorageKey, workspaceStateStorageKey]);

  useEffect(() => {
    if (!workspaceStateReady || !workspaceStateStorageKey) return;
    if (typeof window === "undefined") return;
    const nextState: TaskGraphWorkspaceStoredState = {
      sidebarExpanded,
      inspectorExpanded: false,
      inspectorWorkspace,
      readinessExpanded,
      latestRunExpanded,
      recoveryExpanded,
    };
    writeStoredTaskGraphWorkspaceState(workspaceStateStorageKey, nextState);
  }, [
    inspectorWorkspace,
    latestRunExpanded,
    readinessExpanded,
    recoveryExpanded,
    sidebarExpanded,
    workspaceStateReady,
    workspaceStateStorageKey,
  ]);

  useEffect(() => {
    if (!panelResizeState) return undefined;
    document.body.classList.add("resizing");
    const handlePointerMove = (event: MouseEvent) => {
      const delta = event.clientX - panelResizeState.startX;
      setSidebarWidth(
        normalizeTaskGraphPanelWidth(
          "left",
          panelResizeState.startWidth + delta,
        ),
      );
    };
    const stopResize = () => setPanelResizeState(null);
    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", stopResize, { once: true });
    window.addEventListener("blur", stopResize, { once: true });
    return () => {
      document.body.classList.remove("resizing");
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", stopResize);
      window.removeEventListener("blur", stopResize);
    };
  }, [panelResizeState]);

  const handleSelectTemplate = (templateId: string) => {
    selectedTemplateIdRef.current = templateId;
    setSelectedTemplateId(templateId);
  };

  const handleInstantiateSelectedTemplate = () => {
    const templateId =
      selectedTemplateIdRef.current || templates[0]?.template_id;
    if (!templateId) return;
    setTemplateBrowserOpen(false);
    onInstantiateTemplate(templateId);
  };

  const openTemplateBrowser = () => {
    modalReturnFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    setTemplateBrowserOpen(true);
  };

  const closeTemplateBrowser = () => {
    setTemplateBrowserOpen(false);
    modalReturnFocusRef.current?.focus();
  };

  const openInspectorDialog = (workspace?: "selection" | "run") => {
    modalReturnFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    if (workspace) {
      setInspectorWorkspace(workspace);
      setSelectionInspectorRequested(workspace === "selection");
      setRunInspectorRequested(workspace === "run");
      writePendingRunInspectorReopen(
        pendingRunInspectorStorageKey,
        workspace === "run",
      );
    }
    setInspectorExpanded(true);
  };

  const closeInspectorDialog = () => {
    writePendingRunInspectorReopen(pendingRunInspectorStorageKey, false);
    setInspectorExpanded(false);
    setSelectionInspectorRequested(false);
    setRunInspectorRequested(false);
    modalReturnFocusRef.current?.focus();
  };

  const handleInspectorWorkspaceSelect = (workspace: "selection" | "run") => {
    setSelectionInspectorRequested(workspace === "selection");
    setInspectorWorkspace(workspace);
    if (workspace === "run") {
      setRunInspectorRequested(true);
    }
  };

  const startPanelResize = (side: "left", clientX: number) => {
    setPanelResizeState({
      side,
      startX: clientX,
      startWidth: sidebarWidth,
    });
  };

  const handlePanelResizeKeyDown = (
    side: "left",
    event: ReactKeyboardEvent<HTMLDivElement>,
  ) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const delta = event.key === "ArrowLeft" ? -18 : 18;
    setSidebarWidth((current) =>
      normalizeTaskGraphPanelWidth(side, current + delta),
    );
  };

  return {
    readinessExpanded,
    setReadinessExpanded,
    latestRunExpanded,
    setLatestRunExpanded,
    recoveryExpanded,
    setRecoveryExpanded,
    inspectorWorkspace,
    setInspectorWorkspace,
    selectionInspectorRequested,
    setSelectionInspectorRequested,
    runInspectorRequested,
    setRunInspectorRequested,
    sidebarExpanded,
    setSidebarExpanded,
    inspectorExpanded,
    setInspectorExpanded,
    panelResizeState,
    sidebarWidth,
    setSidebarWidth,
    selectedTemplateId,
    selectedTemplateIdRef,
    templateBrowserOpen,
    setTemplateBrowserOpen,
    modalReturnFocusRef,
    workspaceStateStorageKey,
    workspaceStateReady,
    pendingRunInspectorStorageKey,
    handleSelectTemplate,
    handleInstantiateSelectedTemplate,
    openTemplateBrowser,
    closeTemplateBrowser,
    openInspectorDialog,
    closeInspectorDialog,
    handleInspectorWorkspaceSelect,
    startPanelResize,
    handlePanelResizeKeyDown,
  };
}
