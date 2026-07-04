import {
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
} from "lucide-react";

import { StarbridgeSearchIcon, StarbridgeTaskIcon, StarbridgeWorkflowDefaultIcon } from "../brand/StarbridgeIcons";
import type { LocaleCode } from "../../types";
import { SetupLandingPanel, type SetupLandingAction, type SetupLandingMetric } from "./SetupLandingPanel";

type ViewWorkspacePanelProps = {
  locale: LocaleCode;
  leftSidebarOpen: boolean;
  rightSidebarOpen: boolean;
  archivedVisible: boolean;
  onOpenSearch: () => void;
  onOpenArchived: () => void;
  onReturnToChat: () => void;
  onToggleLeftSidebar: () => void;
  onToggleRightSidebar: () => void;
};

type ViewCopy = {
  eyebrow: string;
  title: string;
  summary: string;
  quickActions: string;
  currentState: string;
  searchTitle: string;
  searchDetail: string;
  archivedTitle: string;
  archivedDetail: string;
  chatTitle: string;
  chatDetail: string;
  leftOpenTitle: string;
  leftClosedTitle: string;
  leftDetail: string;
  rightOpenTitle: string;
  rightClosedTitle: string;
  rightDetail: string;
  keyboardHint: string;
  open: string;
  hidden: string;
  armed: string;
  off: string;
  active: string;
  inactive: string;
  primaryAction: string;
  archivedAction: string;
  returnAction: string;
};

function viewCopy(locale: LocaleCode): ViewCopy {
  if (locale === "zh-CN") {
    return {
      eyebrow: "工作区",
      title: "视图",
      summary: "把搜索、归档任务入口和左右栏显隐集中到这里。它是视图类操作的落地页，不再依赖一级菜单只弹出子菜单。",
      quickActions: "快速操作",
      currentState: "当前状态",
      searchTitle: "搜索当前工作区",
      searchDetail: "返回对话并打开命令面板，继续检索任务、文件或指令。",
      archivedTitle: "打开归档任务",
      archivedDetail: "回到对话区并切换到归档任务列表，方便继续查看旧任务。",
      chatTitle: "返回当前对话",
      chatDetail: "退出视图页，回到当前任务窗口。",
      leftOpenTitle: "收起左侧栏",
      leftClosedTitle: "展开左侧栏",
      leftDetail: "给任务树和项目列表更多空间，或为主画布释放宽度。",
      rightOpenTitle: "收起右侧栏",
      rightClosedTitle: "展开右侧栏",
      rightDetail: "控制状态、审查、浏览器和文件检查区是否在对话页出现。",
      keyboardHint: "Ctrl+K",
      open: "已展开",
      hidden: "已收起",
      armed: "返回对话后显示",
      off: "保持隐藏",
      active: "已打开",
      inactive: "未打开",
      primaryAction: "执行",
      archivedAction: "打开",
      returnAction: "返回",
    };
  }
  return {
    eyebrow: "Workspace",
    title: "View",
    summary: "Centralize search, archived-task access, and pane visibility here. This page is the landing surface for view operations instead of treating the top-level menu as a pure popover.",
    quickActions: "Quick actions",
    currentState: "Current state",
    searchTitle: "Search the workspace",
    searchDetail: "Return to chat and open the command palette to find tasks, files, or prompts.",
    archivedTitle: "Open archived tasks",
    archivedDetail: "Return to chat with the archived task list visible so older work stays reachable.",
    chatTitle: "Return to current chat",
    chatDetail: "Leave the view page and go back to the active task window.",
    leftOpenTitle: "Hide left sidebar",
    leftClosedTitle: "Show left sidebar",
    leftDetail: "Trade task-tree space for more room in the main canvas.",
    rightOpenTitle: "Hide right inspector",
    rightClosedTitle: "Show right inspector",
    rightDetail: "Control whether status, review, browser, and files appear beside the chat canvas.",
    keyboardHint: "Ctrl+K",
    open: "open",
    hidden: "hidden",
    armed: "ready in chat",
    off: "off",
    active: "active",
    inactive: "inactive",
    primaryAction: "Run",
    archivedAction: "Open",
    returnAction: "Return",
  };
}

export function ViewWorkspacePanel({
  locale,
  leftSidebarOpen,
  rightSidebarOpen,
  archivedVisible,
  onOpenSearch,
  onOpenArchived,
  onReturnToChat,
  onToggleLeftSidebar,
  onToggleRightSidebar,
}: ViewWorkspacePanelProps) {
  const copy = viewCopy(locale);
  const stateItems: SetupLandingMetric[] = [
    {
      id: "left",
      label: locale === "zh-CN" ? "左侧栏" : "Left sidebar",
      value: leftSidebarOpen ? copy.open : copy.hidden,
    },
    {
      id: "right",
      label: locale === "zh-CN" ? "右侧栏" : "Right inspector",
      value: rightSidebarOpen ? copy.armed : copy.off,
    },
    {
      id: "archived",
      label: locale === "zh-CN" ? "归档任务" : "Archived tasks",
      value: archivedVisible ? copy.active : copy.inactive,
    },
    {
      id: "shortcut",
      label: locale === "zh-CN" ? "搜索快捷键" : "Search shortcut",
      value: copy.keyboardHint,
    },
  ];
  const actions: SetupLandingAction[] = [
    {
      id: "search",
      icon: <StarbridgeSearchIcon size={15} strokeWidth={1.9} />,
      title: copy.searchTitle,
      detail: copy.searchDetail,
      status: copy.keyboardHint,
      actionLabel: copy.primaryAction,
      onClick: onOpenSearch,
    },
    {
      id: "archived",
      icon: <StarbridgeTaskIcon size={15} strokeWidth={1.9} />,
      title: copy.archivedTitle,
      detail: copy.archivedDetail,
      status: archivedVisible ? copy.active : copy.inactive,
      actionLabel: copy.archivedAction,
      onClick: onOpenArchived,
    },
    {
      id: "left",
      icon: leftSidebarOpen ? <PanelLeftClose size={15} /> : <PanelLeftOpen size={15} />,
      title: leftSidebarOpen ? copy.leftOpenTitle : copy.leftClosedTitle,
      detail: copy.leftDetail,
      status: leftSidebarOpen ? copy.open : copy.hidden,
      actionLabel: copy.primaryAction,
      onClick: onToggleLeftSidebar,
    },
    {
      id: "right",
      icon: rightSidebarOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />,
      title: rightSidebarOpen ? copy.rightOpenTitle : copy.rightClosedTitle,
      detail: copy.rightDetail,
      status: rightSidebarOpen ? copy.armed : copy.off,
      actionLabel: copy.primaryAction,
      onClick: onToggleRightSidebar,
    },
    {
      id: "chat",
      icon: <StarbridgeWorkflowDefaultIcon size={15} strokeWidth={1.9} />,
      title: copy.chatTitle,
      detail: copy.chatDetail,
      status: locale === "zh-CN" ? "任务窗口" : "Task window",
      actionLabel: copy.returnAction,
      onClick: onReturnToChat,
    },
  ];

  return (
    <SetupLandingPanel
      testId="workspace-view-panel"
      eyebrow={copy.eyebrow}
      title={copy.title}
      summary={copy.summary}
      stateLabel={copy.currentState}
      stateItems={stateItems}
      sectionTitle={copy.quickActions}
      actions={actions}
    />
  );
}
