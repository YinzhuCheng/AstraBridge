import { invoke, isTauri } from "@tauri-apps/api/core";

type DialogPath = string | { path?: string; file?: string } | null | undefined;
type DialogPathList = DialogPath | DialogPath[];

function normalizeDialogPath(value: DialogPath): string | null {
  if (!value) return null;
  if (typeof value === "string") return value;
  return value.path ?? value.file ?? null;
}

function ensureProjectSuffix(path: string): string {
  if (path.toLowerCase().endsWith(".abproj")) return path;
  return `${path}.abproj`;
}

async function invokeDialog<T>(command: string, options: Record<string, unknown>): Promise<T | null> {
  if (!isTauri()) return null;
  return invoke<T | null>(command, { options });
}

export async function selectExistingProject(): Promise<string | null> {
  const selected = await invokeDialog<DialogPath>("plugin:dialog|open", {
    title: "Open AstraBridge project",
    multiple: false,
    directory: false,
    filters: [{ name: "AstraBridge Project", extensions: ["abproj"] }],
  });
  return normalizeDialogPath(selected);
}

export async function chooseProjectSavePath(defaultPath: string): Promise<string | null> {
  const selected = await invokeDialog<DialogPath>("plugin:dialog|save", {
    title: "Create AstraBridge project",
    defaultPath,
    filters: [{ name: "AstraBridge Project", extensions: ["abproj"] }],
  });
  const normalized = normalizeDialogPath(selected);
  return normalized ? ensureProjectSuffix(normalized) : null;
}

export async function selectDirectory(title = "Select folder"): Promise<string | null> {
  const selected = await invokeDialog<DialogPath>("plugin:dialog|open", {
    title,
    multiple: false,
    directory: true,
  });
  return normalizeDialogPath(selected);
}

export async function selectFiles(title = "Select files"): Promise<string[]> {
  const selected = await invokeDialog<DialogPathList>("plugin:dialog|open", {
    title,
    multiple: true,
    directory: false,
  });
  if (!selected) return [];
  if (Array.isArray(selected)) {
    return selected.map((item) => normalizeDialogPath(item)).filter((item): item is string => Boolean(item));
  }
  const normalized = normalizeDialogPath(selected);
  return normalized ? [normalized] : [];
}

export async function selectAttachmentFiles(title = "Select attachments"): Promise<string[]> {
  return selectFiles(title);
}

export async function selectAttachmentDirectory(title = "Select attachment folder"): Promise<string | null> {
  return selectDirectory(title);
}

