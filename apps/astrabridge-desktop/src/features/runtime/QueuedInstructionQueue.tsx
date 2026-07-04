import { ChevronDown, ChevronUp, Pencil, SendHorizontal } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import type { AttachmentDraft, LocaleCode } from "../../types";

export type QueuedInstructionQueueItem = {
  id: string;
  text: string;
  attachments: AttachmentDraft[];
};

type QueuedInstructionQueueProps = {
  locale: LocaleCode;
  items: QueuedInstructionQueueItem[];
  expanded: boolean;
  editingId: string | null;
  busyId: string | null;
  blockedId: string | null;
  onToggleExpanded: () => void;
  onEdit: (id: string) => void;
  onCancelEdit: () => void;
  onSaveEdit: (id: string, text: string) => void;
  onSendNow: (id: string) => void;
};

const SUMMARY_LIMIT = 64;

function copy(locale: LocaleCode) {
  if (locale === "zh-CN") {
    return {
      title: "排队中的消息",
      count: (count: number) => `${count} 条`,
      collapse: "收起排队消息",
      expand: "展开排队消息",
      attachmentMessage: "附件消息",
      attachments: (count: number) => `${count} 个附件`,
      edit: "编辑消息",
      sendNow: "立即发送",
      save: "保存",
      cancel: "取消",
      editingLabel: "编辑排队消息",
      blocked: "上次发送失败，已保留在队列",
      sending: "发送中",
    };
  }
  return {
    title: "Queued messages",
    count: (count: number) => `${count}`,
    collapse: "Collapse queued messages",
    expand: "Expand queued messages",
    attachmentMessage: "Attachment message",
    attachments: (count: number) => `${count} attachment${count === 1 ? "" : "s"}`,
    edit: "Edit queued message",
    sendNow: "Send now",
    save: "Save",
    cancel: "Cancel",
    editingLabel: "Edit queued message",
    blocked: "Previous send failed and remains queued",
    sending: "Sending",
  };
}

export function summarizeQueuedInstruction(item: QueuedInstructionQueueItem, locale: LocaleCode) {
  const labels = copy(locale);
  const firstParagraph = item.text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean);
  const normalized = (firstParagraph ?? "").replace(/\s+/g, " ");
  const body =
    normalized.length > SUMMARY_LIMIT
      ? `${normalized.slice(0, SUMMARY_LIMIT).trimEnd()}...`
      : normalized;
  const attachmentCount = item.attachments.length;
  if (!body) {
    return attachmentCount > 0
      ? `${labels.attachmentMessage} · ${labels.attachments(attachmentCount)}`
      : "";
  }
  return attachmentCount > 0 ? `${body} · + ${labels.attachments(attachmentCount)}` : body;
}

export function QueuedInstructionQueue({
  locale,
  items,
  expanded,
  editingId,
  busyId,
  blockedId,
  onToggleExpanded,
  onEdit,
  onCancelEdit,
  onSaveEdit,
  onSendNow,
}: QueuedInstructionQueueProps) {
  const labels = useMemo(() => copy(locale), [locale]);
  const editingItem = items.find((item) => item.id === editingId) ?? null;
  const [draft, setDraft] = useState("");

  useEffect(() => {
    setDraft(editingItem?.text ?? "");
  }, [editingItem?.id, editingItem?.text]);

  if (items.length === 0) return null;

  return (
    <section className={`queued-instruction-card ${expanded ? "queued-instruction-card-expanded" : ""}`} data-testid="queued-instruction-card" aria-label={labels.title}>
      <button type="button" className="queued-instruction-head" onClick={onToggleExpanded} aria-expanded={expanded}>
        <span>
          <strong>{labels.title}</strong>
          <em>{labels.count(items.length)}</em>
        </span>
        {expanded ? <ChevronUp size={15} strokeWidth={1.8} aria-hidden="true" /> : <ChevronDown size={15} strokeWidth={1.8} aria-hidden="true" />}
      </button>
      {expanded ? (
        <div className="queued-instruction-list" role="list">
          {items.map((item) => {
            const isEditing = item.id === editingId;
            const isBusy = item.id === busyId;
            const isBlocked = item.id === blockedId;
            const canSave = draft.trim().length > 0 || item.attachments.length > 0;
            return (
              <div className={`queued-instruction-row ${isEditing ? "queued-instruction-row-editing" : ""}`} role="listitem" key={item.id}>
                {isEditing ? (
                  <div className="queued-instruction-editor">
                    <textarea aria-label={labels.editingLabel} value={draft} onChange={(event) => setDraft(event.target.value)} rows={3} />
                    <div className="queued-instruction-editor-actions">
                      <button type="button" className="primary-button" disabled={!canSave || isBusy} onClick={() => onSaveEdit(item.id, draft)}>
                        {labels.save}
                      </button>
                      <button type="button" className="ghost-button" disabled={isBusy} onClick={onCancelEdit}>
                        {labels.cancel}
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="queued-instruction-summary">
                      <span>{summarizeQueuedInstruction(item, locale)}</span>
                      {isBlocked ? <small>{labels.blocked}</small> : null}
                      {isBusy ? <small>{labels.sending}</small> : null}
                    </div>
                    <div className="queued-instruction-actions">
                      <button type="button" className="icon-button" disabled={Boolean(busyId)} onClick={() => onEdit(item.id)} title={labels.edit} aria-label={labels.edit}>
                        <Pencil size={14} strokeWidth={1.8} aria-hidden="true" />
                      </button>
                      <button type="button" className="icon-button" disabled={Boolean(busyId)} onClick={() => onSendNow(item.id)} title={labels.sendNow} aria-label={labels.sendNow}>
                        <SendHorizontal size={14} strokeWidth={1.8} aria-hidden="true" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
