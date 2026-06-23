import { Files, GitCompare, Globe2, ListChecks, Terminal } from "lucide-react";
import type { ReactNode } from "react";
import { t } from "../i18n/catalog";
import type {
  ProjectFile,
  ProjectFilePreview,
  ProjectFilesTree,
  ProjectReviewDiff,
  ProjectReviewStatus,
  ProjectTerminalHistory,
  RuntimeSupervisorState,
} from "../../types";
import type { CodingEventInspectorSummary } from "./codingEventInspector";
import type { TaskWorkflowFacts } from "./taskWorkflowFacts";

export type InspectorTab = "status" | "review" | "terminal" | "browser" | "files";

type Locale = "en" | "zh-CN";

type BrowserSmokeSummary = {
  label?: string;
  status?: string;
  url?: string;
  console_errors?: string[];
  request_failures?: Array<{ url?: string; method?: string; resource_type?: string; error_text?: string }>;
  screenshot_path?: string;
} | null;

function InspectorTabButton({
  tab,
  active,
  icon,
  label,
  onClick,
}: {
  tab: InspectorTab;
  active: boolean;
  icon: ReactNode;
  label: string;
  onClick: (tab: InspectorTab) => void;
}) {
  return (
    <button type="button" data-testid={`inspector-tab-${tab}`} className={`inspector-tab-button ${active ? "active" : ""}`} onClick={() => onClick(tab)} title={label}>
      {icon}
      <span>{label}</span>
    </button>
  );
}

export function InspectorTabBar({
  locale,
  activeTab,
  onChange,
}: {
  locale: Locale;
  activeTab: InspectorTab;
  onChange: (tab: InspectorTab) => void;
}) {
  return (
    <nav className="inspector-tabbar" aria-label="Inspector views">
      <InspectorTabButton tab="status" active={activeTab === "status"} icon={<ListChecks size={14} aria-hidden="true" />} label={t(locale, "inspector_status")} onClick={onChange} />
      <InspectorTabButton tab="review" active={activeTab === "review"} icon={<GitCompare size={14} aria-hidden="true" />} label={t(locale, "inspector_review")} onClick={onChange} />
      <InspectorTabButton tab="terminal" active={activeTab === "terminal"} icon={<Terminal size={14} aria-hidden="true" />} label={t(locale, "inspector_terminal")} onClick={onChange} />
      <InspectorTabButton tab="browser" active={activeTab === "browser"} icon={<Globe2 size={14} aria-hidden="true" />} label={t(locale, "inspector_browser")} onClick={onChange} />
      <InspectorTabButton tab="files" active={activeTab === "files"} icon={<Files size={14} aria-hidden="true" />} label={t(locale, "inspector_files")} onClick={onChange} />
    </nav>
  );
}

export function ReviewInspectorPanel({
  locale,
  supervisor,
  review,
  diff,
  fallback,
  selectedPath,
  onSelectPath,
}: {
  locale: Locale;
  supervisor?: RuntimeSupervisorState;
  review?: ProjectReviewStatus;
  diff?: ProjectReviewDiff;
  fallback?: CodingEventInspectorSummary;
  selectedPath?: string;
  onSelectPath: (path: string) => void;
}) {
  const git = review?.git ?? supervisor?.environment.git;
  const files = (review?.files?.length ? review.files : fallback?.reviewFiles) ?? [];
  const fallbackDetail = selectedPath ? fallback?.detailByPath[selectedPath] : "";
  return (
    <section className="inspector-tool-panel" data-testid="review-panel">
      <div className="section-header">
        <h2>{t(locale, "review_title")}</h2>
        <span className="diff-progress-pill">
          <span className="diff-added">+{(git?.added ?? 0).toLocaleString()}</span>
          <span className="diff-deleted">-{(git?.deleted ?? 0).toLocaleString()}</span>
        </span>
      </div>
      <div className="tool-list">
        <div className="tool-row">
          <span>{t(locale, "review_changed_files")}</span>
          <strong>{git?.changed_files ?? 0}</strong>
        </div>
        <div className="tool-row">
          <span>{t(locale, "review_git_status")}</span>
          <strong>{git?.is_repo ? git.branch || "repo" : t(locale, "inspector_non_git")}</strong>
        </div>
      </div>
      <div className="inspector-list" role="list" aria-label={t(locale, "review_changed_files")}>
        {files.length ? (
          files.slice(0, 12).map((file) => (
            <button
              type="button"
              data-testid="review-file-row"
              className={`inspector-list-row ${selectedPath === file.path ? "active" : ""}`}
              onClick={() => onSelectPath(file.path)}
              key={`${file.status}:${file.path}`}
            >
              <span>{file.path}</span>
              <small>{file.status}</small>
            </button>
          ))
        ) : (
          <p className="muted compact-copy">{t(locale, "review_empty")}</p>
        )}
      </div>
      {diff ? (
        <pre className="tool-preview diff-preview">{diff.ok ? diff.diff || t(locale, "review_no_diff") : diff.error || t(locale, "review_diff_error")}</pre>
      ) : fallbackDetail ? (
        <pre className="tool-preview diff-preview">{fallbackDetail}</pre>
      ) : (
        <p className="muted compact-copy">{t(locale, "review_select_file")}</p>
      )}
    </section>
  );
}

export function TerminalInspectorPanel({
  locale,
  supervisor,
  history,
  fallback,
}: {
  locale: Locale;
  supervisor?: RuntimeSupervisorState;
  history?: ProjectTerminalHistory;
  fallback?: CodingEventInspectorSummary;
}) {
  const commandRows = history?.commands?.length
    ? history.commands.slice(-12).map((item, index) => ({
        key: `${item.timestamp}-${index}`,
        summary: item.summary || item.command,
        status: item.status,
      }))
    : (fallback?.commandRefs ?? []).slice(-12).map((item, index) => ({
        key: `${item.command}:${index}`,
        summary: item.command,
        status: item.status || "event",
      }));
  return (
    <section className="inspector-tool-panel" data-testid="terminal-panel">
      <div className="section-header">
        <h2>{t(locale, "terminal_title")}</h2>
        <span className="status-tag">{history?.execution_host ?? (supervisor?.environment.cwd ? t(locale, "terminal_connected") : t(locale, "terminal_disconnected"))}</span>
      </div>
      <p className="muted compact-copy">{t(locale, "terminal_summary")}</p>
      <pre className="tool-preview">{history?.workspace_root ?? supervisor?.environment.cwd ?? t(locale, "terminal_no_workspace")}</pre>
      <div className="inspector-list" role="list" aria-label={t(locale, "terminal_history")}>
        {commandRows.length ? (
          commandRows.map((item) => (
            <div className="inspector-list-row static-row" data-testid="terminal-command-row" key={item.key}>
              <span>{item.summary}</span>
              <small>{item.status}</small>
            </div>
          ))
        ) : (
          <p className="muted compact-copy">{t(locale, "terminal_empty")}</p>
        )}
      </div>
    </section>
  );
}

export function WorkflowEvidencePanel({
  locale,
  facts,
}: {
  locale: Locale;
  facts: TaskWorkflowFacts;
}) {
  const checkpoints = facts.checkpointRefs;
  const diagnostics = facts.diagnosticRefs;
  return (
    <section className="pane-section inspector-section" data-testid="workflow-evidence-panel">
      <div className="section-header">
        <h2>{t(locale, "workflow_facts")}</h2>
      </div>
      <div className="tool-list">
        <div className="tool-row" data-testid="workflow-fact-lanes">
          <span>{t(locale, "workflow_lanes")}</span>
          <strong>{facts.laneCount}</strong>
        </div>
        <div className="tool-row" data-testid="workflow-fact-handoffs">
          <span>{t(locale, "workflow_handoffs")}</span>
          <strong>{facts.handoffCount}</strong>
        </div>
        <div className="tool-row" data-testid="workflow-fact-checkpoints">
          <span>{t(locale, "workflow_checkpoints")}</span>
          <strong>{facts.checkpointCount}</strong>
        </div>
        <div className="tool-row" data-testid="workflow-fact-commands">
          <span>{t(locale, "workflow_commands")}</span>
          <strong>{facts.commandCount}</strong>
        </div>
        <div className="tool-row" data-testid="workflow-fact-diagnostics">
          <span>{t(locale, "workflow_diagnostics")}</span>
          <strong>{facts.diagnosticCount}</strong>
        </div>
        <div className="tool-row" data-testid="workflow-fact-recovery">
          <span>{t(locale, "workflow_recovery")}</span>
          <strong>
            {facts.recoveredCommandCount > 0
              ? `${facts.recoveredCommandCount} recovered`
              : facts.failedCommandCount > 0
                ? `${facts.failedCommandCount} ${t(locale, "workflow_pending")}`
                : t(locale, "workflow_clear")}
          </strong>
        </div>
      </div>
      {checkpoints.length ? (
        <div className="inspector-list" role="list" aria-label={t(locale, "workflow_checkpoints")}>
          {checkpoints.slice(-4).map((item) => (
            <div className="inspector-list-row static-row" data-testid="workflow-checkpoint-row" key={item.save_id}>
              <span>{item.description}</span>
              <small>{item.save_id}</small>
            </div>
          ))}
        </div>
      ) : null}
      {diagnostics.length ? (
        <div className="inspector-list" role="list" aria-label={t(locale, "workflow_diagnostics")}>
          {diagnostics.slice(-4).map((item, index) => (
            <div className="inspector-list-row static-row" data-testid="workflow-diagnostic-row" key={`${item.kind}:${item.summary}:${index}`}>
              <span>{item.summary}</span>
              <small>{item.kind}</small>
            </div>
          ))}
        </div>
      ) : !checkpoints.length ? (
        <p className="muted compact-copy">{t(locale, "workflow_empty")}</p>
      ) : null}
    </section>
  );
}

export function BrowserInspectorPanel({
  locale,
  supervisor,
  latestSmoke,
  statusLabel,
  isPreparingWorkflowDemo,
  isPreparingNativeKernelDemo,
  isRunningReleaseSmoke,
  isRunningProviderSwitchSmoke,
  isRunningNativeKernelSmoke,
  onPrepareWorkflowDemo,
  onPrepareNativeKernelDemo,
  onRunReleaseSmoke,
  onRunProviderSwitchSmoke,
  onRunNativeKernelSmoke,
}: {
  locale: Locale;
  supervisor?: RuntimeSupervisorState;
  latestSmoke?: BrowserSmokeSummary;
  statusLabel: (value: string | null | undefined) => string;
  isPreparingWorkflowDemo?: boolean;
  isPreparingNativeKernelDemo?: boolean;
  isRunningReleaseSmoke?: boolean;
  isRunningProviderSwitchSmoke?: boolean;
  isRunningNativeKernelSmoke?: boolean;
  onPrepareWorkflowDemo: () => void;
  onPrepareNativeKernelDemo: () => void;
  onRunReleaseSmoke: () => void;
  onRunProviderSwitchSmoke: () => void;
  onRunNativeKernelSmoke: () => void;
}) {
  const browser = latestSmoke ?? supervisor?.browser;
  return (
    <section className="inspector-tool-panel" data-testid="browser-panel">
      <div className="section-header">
        <h2>{t(locale, "browser_title")}</h2>
        <span className={`status-tag ${browser?.status === "pass" ? "status-ok" : ""}`}>{browser?.status ? statusLabel(browser.status) : t(locale, "inspector_not_run")}</span>
      </div>
      {browser ? (
        <div className="tool-list">
          <div className="tool-row">
            <span>{t(locale, "browser_label")}</span>
            <strong>{browser.label || "-"}</strong>
          </div>
          <div className="tool-row">
            <span>URL</span>
            <strong>{browser.url || "-"}</strong>
          </div>
          <div className="tool-row">
            <span>{t(locale, "browser_console")}</span>
            <strong>{browser.console_errors?.length ?? 0}</strong>
          </div>
          <div className="tool-row">
            <span>{t(locale, "browser_request_failures")}</span>
            <strong>{browser.request_failures?.length ?? 0}</strong>
          </div>
          {browser.screenshot_path ? (
            <div className="tool-row tool-row-wide">
              <span>{t(locale, "browser_screenshot")}</span>
              <strong title={browser.screenshot_path}>{browser.screenshot_path}</strong>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="muted compact-copy">{t(locale, "browser_empty")}</p>
      )}
      {browser?.request_failures?.length ? (
        <pre className="tool-preview">
          {browser.request_failures
            .slice(0, 4)
            .map((item) => [item.method, item.resource_type, item.error_text, item.url].filter(Boolean).join(" | "))
            .join("\n")}
        </pre>
      ) : null}
      <div className="inspector-actions">
        <button type="button" data-testid="prepare-release-workflow-demo" className="ghost-button inspector-inline-action" disabled={isPreparingWorkflowDemo} onClick={onPrepareWorkflowDemo}>
          {isPreparingWorkflowDemo ? t(locale, "browser_preparing") : t(locale, "browser_prepare_release")}
        </button>
        <button type="button" data-testid="prepare-native-kernel-demo" className="ghost-button inspector-inline-action" disabled={isPreparingNativeKernelDemo} onClick={onPrepareNativeKernelDemo}>
          {isPreparingNativeKernelDemo ? t(locale, "browser_preparing") : t(locale, "browser_prepare_native")}
        </button>
        <button type="button" className="ghost-button inspector-inline-action" disabled={isRunningReleaseSmoke} onClick={onRunReleaseSmoke}>
          {isRunningReleaseSmoke ? t(locale, "browser_running") : t(locale, "browser_run_release")}
        </button>
        <button type="button" className="ghost-button inspector-inline-action" disabled={isRunningProviderSwitchSmoke} onClick={onRunProviderSwitchSmoke}>
          {isRunningProviderSwitchSmoke ? t(locale, "browser_running") : t(locale, "browser_run_provider_switch")}
        </button>
        <button type="button" className="ghost-button inspector-inline-action" disabled={isRunningNativeKernelSmoke} onClick={onRunNativeKernelSmoke}>
          {isRunningNativeKernelSmoke ? t(locale, "browser_running") : t(locale, "browser_run_native")}
        </button>
      </div>
    </section>
  );
}

export function FilesInspectorPanel({
  locale,
  project,
  tree,
  preview,
  fallback,
  query,
  selectedPath,
  onQueryChange,
  onSelectPath,
}: {
  locale: Locale;
  project: ProjectFile;
  tree?: ProjectFilesTree;
  preview?: ProjectFilePreview;
  fallback?: CodingEventInspectorSummary;
  query: string;
  selectedPath?: string;
  onQueryChange: (value: string) => void;
  onSelectPath: (path: string) => void;
}) {
  const items = (tree?.items?.length ? tree.items : fallback?.recentFiles) ?? [];
  const fallbackDetail = selectedPath ? fallback?.detailByPath[selectedPath] : "";
  return (
    <section className="inspector-tool-panel" data-testid="files-panel">
      <div className="section-header">
        <h2>{t(locale, "files_title")}</h2>
        <span className="status-tag">{items.length}</span>
      </div>
      <input className="inspector-search" value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder={t(locale, "files_filter")} aria-label={t(locale, "files_filter")} />
      <div className="inspector-list inspector-file-list" role="list" aria-label={t(locale, "files_title")}>
        {items.slice(0, 18).map((item) => (
          <button
            type="button"
            data-testid="project-file-row"
            className={`inspector-list-row ${selectedPath === item.path ? "active" : ""}`}
            onClick={() => onSelectPath(item.path)}
            key={item.path}
          >
            <span>{item.path}</span>
            <small>{item.kind}</small>
          </button>
        ))}
        {!items.length ? <p className="muted compact-copy">{t(locale, "files_empty")}</p> : null}
      </div>
      {preview ? (
        <div className="file-preview">
          <div className="tool-row">
            <span>{preview.path}</span>
            <strong>{Math.round((preview.size || 0) / 1024)} KB</strong>
          </div>
          {preview.kind === "image" && preview.data_url ? <img src={preview.data_url} alt={preview.name} /> : null}
          {preview.kind === "text" ? <pre className="tool-preview">{preview.content}</pre> : null}
          {preview.kind !== "text" && preview.kind !== "image" ? <p className="muted compact-copy">{preview.message ?? t(locale, "files_unsupported")}</p> : null}
        </div>
      ) : fallbackDetail ? (
        <div className="file-preview">
          <div className="tool-row">
            <span>{selectedPath}</span>
            <strong>{t(locale, "files_event_summary")}</strong>
          </div>
          <pre className="tool-preview">{fallbackDetail}</pre>
        </div>
      ) : (
        <pre className="tool-preview">{project.workspace_root}</pre>
      )}
    </section>
  );
}
