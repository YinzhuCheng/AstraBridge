import { useEffect, useMemo, useState } from "react";

import { api as defaultApi } from "../../api";
import type {
  DesktopUpdateRehearsalResult,
  DesktopUpdateStatus,
  ProjectFile,
  UpdateChannel,
} from "../../types";

type DesktopUpdateApi = {
  status: () => Promise<DesktopUpdateStatus>;
  saveChannel: (channel: UpdateChannel) => Promise<{ project: ProjectFile }>;
  rehearsal: (payload?: { run_id?: string | null }) => Promise<DesktopUpdateRehearsalResult>;
};

type DesktopUpdatePanelProps = {
  locale: "en" | "zh-CN";
  project: ProjectFile;
  onProjectUpdated: (project: ProjectFile) => void;
  api?: DesktopUpdateApi;
};

function fileHref(path: string | null | undefined) {
  const normalized = String(path || "").trim();
  if (!normalized) return "";
  if (/^[A-Za-z]:[\\/]/.test(normalized)) return `file:///${normalized.replace(/\\/g, "/")}`;
  if (normalized.startsWith("/")) return `file://${normalized}`;
  return "";
}

function updateCopy(locale: "en" | "zh-CN") {
  return locale === "zh-CN"
    ? {
        eyebrow: "产品更新",
        title: "桌面更新通道与隔离演练",
        subtitle: "显式选择 stable / beta / canary，查看 kill switch 状态，并在隔离 Windows 演练路径上验证 formal bundle、激活和回滚入口。",
        channel: "更新通道",
        killSwitch: "Kill switch",
        formalBundle: "Formal bundle",
        rehearsal: "Windows 隔离演练",
        selectedEndpoint: "当前通道 endpoint",
        installMode: "Windows 安装模式",
        status: "状态",
        saveBusy: "保存中...",
        rehearse: "运行隔离演练",
        rehearseBusy: "演练中...",
        refresh: "刷新",
        defaultChannel: "默认通道",
        loadedFromDisk: "已从磁盘 manifest 读取",
        updatesEnabled: "允许更新",
        latestRun: "最近演练",
        artifact: "产物",
        warnings: "警告",
        none: "暂无",
        endpointMissing: "未解析到 endpoint",
        contract: "Updater 契约",
        bundleReady: "Formal bundle 已就绪",
        bundleIncomplete: "Formal bundle 不完整",
        cleanInstall: "Clean install 检查",
        channelUpdate: "Channel-aware update 检查",
        rollback: "Rollback 检查",
        selected: "当前选择",
        generatedAt: "生成时间",
      }
    : {
        eyebrow: "Product updates",
        title: "Desktop channels and isolated rehearsal",
        subtitle: "Choose stable / beta / canary explicitly, inspect kill-switch state, and validate the formal bundle plus activation/rollback entry points in an isolated Windows rehearsal path.",
        channel: "Update channel",
        killSwitch: "Kill switch",
        formalBundle: "Formal bundle",
        rehearsal: "Windows isolated rehearsal",
        selectedEndpoint: "Selected channel endpoint",
        installMode: "Windows install mode",
        status: "Status",
        saveBusy: "Saving...",
        rehearse: "Run isolated rehearsal",
        rehearseBusy: "Running rehearsal...",
        refresh: "Refresh",
        defaultChannel: "Default channel",
        loadedFromDisk: "Loaded from disk manifest",
        updatesEnabled: "Updates enabled",
        latestRun: "Latest rehearsal",
        artifact: "Artifact",
        warnings: "Warnings",
        none: "None",
        endpointMissing: "No endpoint resolved",
        contract: "Updater contract",
        bundleReady: "Formal bundle ready",
        bundleIncomplete: "Formal bundle incomplete",
        cleanInstall: "Clean install check",
        channelUpdate: "Channel-aware update check",
        rollback: "Rollback check",
        selected: "Selected",
        generatedAt: "Generated",
      };
}

export function DesktopUpdatePanel({
  locale,
  project,
  onProjectUpdated,
  api = {
    status: defaultApi.desktopUpdateStatus,
    saveChannel: (channel) => defaultApi.updateProjectPreferences({ update_channel: channel }),
    rehearsal: defaultApi.runDesktopUpdateRehearsal,
  },
}: DesktopUpdatePanelProps) {
  const copy = updateCopy(locale);
  const [status, setStatus] = useState<DesktopUpdateStatus | null>(null);
  const [rehearsal, setRehearsal] = useState<DesktopUpdateRehearsalResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingChannel, setSavingChannel] = useState(false);
  const [runningRehearsal, setRunningRehearsal] = useState(false);
  const [error, setError] = useState("");

  async function refreshStatus() {
    setLoading(true);
    setError("");
    try {
      const nextStatus = await api.status();
      setStatus(nextStatus);
    } catch (refreshError) {
      setError(String((refreshError as Error).message ?? refreshError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshStatus();
  }, [project.project_id, project.ui_preferences.update_channel]);

  const selectedChannel = useMemo<UpdateChannel>(() => {
    const fromProject = project.ui_preferences.update_channel;
    if (fromProject) return fromProject;
    return status?.selected_channel ?? status?.default_channel ?? "stable";
  }, [project.ui_preferences.update_channel, status?.default_channel, status?.selected_channel]);

  async function changeChannel(channel: UpdateChannel) {
    if (channel === selectedChannel) return;
    setSavingChannel(true);
    setError("");
    try {
      const response = await api.saveChannel(channel);
      onProjectUpdated(response.project);
      const nextStatus = await api.status();
      setStatus(nextStatus);
    } catch (saveError) {
      setError(String((saveError as Error).message ?? saveError));
    } finally {
      setSavingChannel(false);
    }
  }

  async function runRehearsal() {
    setRunningRehearsal(true);
    setError("");
    try {
      const result = await api.rehearsal();
      setRehearsal(result);
      const nextStatus = await api.status();
      setStatus(nextStatus);
    } catch (runError) {
      setError(String((runError as Error).message ?? runError));
    } finally {
      setRunningRehearsal(false);
    }
  }

  return (
    <div className="manager-panel" data-testid="desktop-update-panel">
      <div className="manager-hero">
        <div>
          <span className="eyebrow">{copy.eyebrow}</span>
          <h3>{copy.title}</h3>
          <p className="muted">{copy.subtitle}</p>
        </div>
        <span className="session-badge">{status?.updater_contract_status ?? "loading"}</span>
      </div>

      <div className="manager-grid">
        <section className="manager-section">
          <h4>{copy.channel}</h4>
          <label className="field">
            <span>{copy.selected}</span>
            <select
              data-testid="desktop-update-channel"
              value={selectedChannel}
              disabled={savingChannel || loading}
              onChange={(event) => void changeChannel(event.target.value as UpdateChannel)}
            >
              {(status?.channels ?? []).map((channel) => (
                <option key={channel.channel} value={channel.channel}>
                  {channel.channel}{channel.default ? ` (${copy.defaultChannel})` : ""}
                </option>
              ))}
            </select>
          </label>
          <div className="manager-list">
            <div className="manager-row">
              <span>
                <strong>{copy.selectedEndpoint}</strong>
                <small>{status?.selected_endpoint || copy.endpointMissing}</small>
              </span>
            </div>
            <div className="manager-row">
              <span>
                <strong>{copy.installMode}</strong>
                <small>{status?.tauri_runtime.windows_install_mode ?? "-"}</small>
              </span>
            </div>
            <div className="manager-row">
              <span>
                <strong>{copy.generatedAt}</strong>
                <small>{status?.generated_at ?? "-"}</small>
              </span>
            </div>
          </div>
          <div className="field-row">
            <button type="button" className="ghost-button" onClick={() => void refreshStatus()} disabled={loading || savingChannel || runningRehearsal}>
              {copy.refresh}
            </button>
            {savingChannel ? <span className="muted">{copy.saveBusy}</span> : null}
          </div>
        </section>

        <section className="manager-section">
          <h4>{copy.killSwitch}</h4>
          <div className="manager-list">
            <div className="manager-row">
              <span>
                <strong>{copy.status}</strong>
                <small>{status?.kill_switch.active_mode ?? "-"}</small>
              </span>
              <code>{status?.kill_switch.updates_enabled ? copy.updatesEnabled : "updates blocked"}</code>
            </div>
            <div className="manager-row">
              <span>
                <strong>{copy.loadedFromDisk}</strong>
                <small>{String(Boolean(status?.kill_switch.loaded_from_disk))}</small>
              </span>
              <code>{status?.kill_switch.source_path ?? "-"}</code>
            </div>
            <div className="manager-row">
              <span>
                <strong>{copy.contract}</strong>
                <small>{status?.kill_switch.default_mode ?? "-"}</small>
              </span>
              <code>{status?.kill_switch.manifest_path ?? "-"}</code>
            </div>
          </div>
        </section>

        <section className="manager-section">
          <h4>{copy.formalBundle}</h4>
          <div className="manager-list">
            <div className="manager-row">
              <span>
                <strong>{copy.status}</strong>
                <small>{status?.formal_bundle.status === "ready" ? copy.bundleReady : copy.bundleIncomplete}</small>
              </span>
            </div>
            <div className="manager-row">
              <span>
                <strong>Launcher</strong>
                <small>{status?.formal_bundle.launcher_path ?? "-"}</small>
              </span>
            </div>
            <div className="manager-row">
              <span>
                <strong>Manifest</strong>
                <small>{status?.formal_bundle.bundle_manifest_path ?? "-"}</small>
              </span>
            </div>
          </div>
        </section>

        <section className="manager-section">
          <h4>{copy.rehearsal}</h4>
          <div className="field-row">
            <button
              type="button"
              className="primary-button"
              data-testid="desktop-update-run-rehearsal"
              disabled={runningRehearsal || loading}
              onClick={() => void runRehearsal()}
            >
              {runningRehearsal ? copy.rehearseBusy : copy.rehearse}
            </button>
          </div>
          <div className="manager-list">
            <div className="manager-row">
              <span>
                <strong>{copy.latestRun}</strong>
                <small>{rehearsal?.run_id ?? status?.latest_rehearsal?.run_id ?? copy.none}</small>
              </span>
              <code>{rehearsal?.status ?? status?.latest_rehearsal?.status ?? "-"}</code>
            </div>
            {rehearsal ? (
              <>
                <div className="manager-row">
                  <span>
                    <strong>{copy.cleanInstall}</strong>
                    <small>{rehearsal.clean_install_check.status}</small>
                  </span>
                </div>
                <div className="manager-row">
                  <span>
                    <strong>{copy.channelUpdate}</strong>
                    <small>{rehearsal.update_check.status}</small>
                  </span>
                </div>
                <div className="manager-row">
                  <span>
                    <strong>{copy.rollback}</strong>
                    <small>{rehearsal.rollback_check.status}</small>
                  </span>
                </div>
              </>
            ) : null}
            {(rehearsal?.artifact_paths.summary_json || status?.latest_rehearsal?.summary_json) ? (
              <div className="manager-row">
                <span>
                  <strong>{copy.artifact}</strong>
                  <a
                    href={fileHref(rehearsal?.artifact_paths.summary_json || status?.latest_rehearsal?.summary_json || "")}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {rehearsal?.artifact_paths.summary_json || status?.latest_rehearsal?.summary_json}
                  </a>
                </span>
              </div>
            ) : null}
          </div>
        </section>
      </div>

      {(status?.warnings?.length || rehearsal?.errors?.length || error) ? (
        <section className="manager-section">
          <h4>{copy.warnings}</h4>
          <div className="manager-list">
            {error ? <p className="error-text" role="alert">{error}</p> : null}
            {(status?.warnings ?? []).map((warning) => (
              <div className="manager-row" key={warning}>
                <span><small>{warning}</small></span>
              </div>
            ))}
            {(rehearsal?.errors ?? []).map((entry) => (
              <div className="manager-row" key={entry}>
                <span><small>{entry}</small></span>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
