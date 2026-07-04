import {
  Brain,
  ChevronDown,
  ChevronRight,
  GitFork,
  Globe2,
  Image as ImageIcon,
  PencilLine,
  Terminal,
  Wrench,
} from "lucide-react";
import { useState } from "react";

import type { LocaleCode, RuntimeActivityEntry, RuntimeActivityKind, RuntimeDiffSummary } from "../../types";
import { runtimeActivityStatusLabel, shortenActivityPath } from "./runtimeActivity";

type RuntimeActivityRowProps = {
  entry: RuntimeActivityEntry;
  locale: LocaleCode;
};

type RuntimeActivityStackProps = {
  entries: RuntimeActivityEntry[];
  locale: LocaleCode;
};

function iconForKind(kind: RuntimeActivityKind) {
  if (kind === "command") return Terminal;
  if (kind === "file_edit" || kind === "file_change") return PencilLine;
  if (kind === "web" || kind === "web_search" || kind === "browser") return Globe2;
  if (kind === "multimodal") return ImageIcon;
  if (kind === "fork") return GitFork;
  if (kind === "thinking") return Brain;
  return Wrench;
}

function hasDetail(entry: RuntimeActivityEntry) {
  return Boolean(entry.detail?.trim() || entry.files?.length || entry.diff?.diff);
}

function detailText(entry: RuntimeActivityEntry) {
  const parts = [
    entry.toolName ? `tool: ${entry.toolName}` : "",
    entry.files?.length ? `files:\n${entry.files.join("\n")}` : "",
    entry.diff ? [`changed files: ${entry.diff.files}`, `added: ${entry.diff.added}`, `deleted: ${entry.diff.deleted}`].join("\n") : "",
    entry.detail ?? "",
    entry.diff?.diff ?? "",
  ].filter(Boolean);
  return parts.join("\n\n");
}

export function DiffDeltaTicker({ diff }: { diff?: RuntimeDiffSummary }) {
  if (!diff || (diff.added === 0 && diff.deleted === 0 && diff.files === 0)) return null;
  const key = `${diff.files}:${diff.added}:${diff.deleted}`;
  return (
    <span className="runtime-activity-diff" data-testid="runtime-activity-diff" data-diff-key={key} title={`${diff.files} changed files`}>
      <span className="runtime-activity-added" key={`added-${key}`}>+{diff.added.toLocaleString()}</span>
      <span className="runtime-activity-deleted" key={`deleted-${key}`}>-{diff.deleted.toLocaleString()}</span>
    </span>
  );
}

export function RuntimeActivityRow({ entry, locale }: RuntimeActivityRowProps) {
  const [expanded, setExpanded] = useState(false);
  const Icon = iconForKind(entry.kind);
  const canExpand = hasDetail(entry);
  const status = runtimeActivityStatusLabel(entry, locale);
  const preview = entry.kind === "file_edit" && entry.files?.length
    ? entry.files.map((file) => shortenActivityPath(file)).slice(0, 2).join(", ")
    : entry.preview;
  const text = [status, preview].filter(Boolean).join(" ");
  const iconLabel = locale === "zh-CN" ? status : status;

  return (
    <section className={`runtime-activity-row runtime-activity-${entry.kind} runtime-activity-status-${entry.status}`} data-testid="runtime-activity-row">
      <button
        type="button"
        className="runtime-activity-toggle"
        disabled={!canExpand}
        aria-expanded={canExpand ? expanded : undefined}
        onClick={() => canExpand && setExpanded((value) => !value)}
        title={text}
      >
        <span className="runtime-activity-leading-icon" title={iconLabel} aria-hidden="true">
          <Icon size={14} strokeWidth={1.75} />
        </span>
        <span className="runtime-activity-text">{text}</span>
        <DiffDeltaTicker diff={entry.diff} />
        {canExpand ? (
          <span className="runtime-activity-expand-icon" aria-hidden="true">
            {expanded ? <ChevronDown size={14} strokeWidth={1.8} /> : <ChevronRight size={14} strokeWidth={1.8} />}
          </span>
        ) : null}
      </button>
      {expanded ? (
        <div className="runtime-activity-detail">
          {entry.files?.length ? (
            <div className="runtime-activity-file-list" aria-label={locale === "zh-CN" ? "编辑文件" : "Edited files"}>
              {entry.files.map((file) => (
                <span key={file} title={file}>{shortenActivityPath(file)}</span>
              ))}
            </div>
          ) : null}
          <pre>{detailText(entry)}</pre>
        </div>
      ) : null}
    </section>
  );
}

export function RuntimeActivityStack({ entries, locale }: RuntimeActivityStackProps) {
  if (entries.length === 0) return null;
  return (
    <div className="runtime-activity-stack" data-testid="runtime-activity-stack">
      {entries.map((entry) => (
        <RuntimeActivityRow key={entry.id} entry={entry} locale={locale} />
      ))}
    </div>
  );
}
