export type ParsedPlanCard = {
  title: string;
  summary: string[];
  steps: string[];
  raw: string;
  isLong: boolean;
};

export type ContextGuardLevel = "ok" | "warning" | "danger" | "pause";

export function extractProposedPlanText(text: string) {
  const match = String(text || "").match(/<proposed_plan>([\s\S]*?)<\/proposed_plan>/i);
  return (match?.[1] ?? "").trim();
}

export function parsePlanCard(text: string): ParsedPlanCard {
  const raw = (extractProposedPlanText(text) || text || "").trim();
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const title = cleanMarkdown(lines.find((line) => /^#{1,3}\s+/.test(line)) || lines[0] || "Plan");
  const summary = collectSection(lines, "summary").slice(0, 5);
  const steps = collectLikelySteps(lines).slice(0, 8);
  return {
    title,
    summary: summary.length > 0 ? summary : lines.filter((line) => /^[-*]\s+/.test(line)).map(cleanMarkdown).slice(0, 4),
    steps,
    raw,
    isLong: raw.length > 900 || lines.length > 16,
  };
}

export function contextGuardLevel(contextPercent: number): ContextGuardLevel {
  if (contextPercent >= 90) return "pause";
  if (contextPercent >= 80) return "danger";
  if (contextPercent >= 70) return "warning";
  return "ok";
}

export function hasUnsafeWindowsWrite(command: string) {
  const text = String(command || "");
  if (!/(Set-Content|Out-File|WriteAllText)/i.test(text)) return false;
  return !/(utf8|utf-8|UTF8Encoding|Encoding\s*=\s*['"]?utf8|NoNewline)/i.test(text);
}

export function readsExplosiveAstraBridgeLog(command: string) {
  return /\.astrabridge[\\/](runtime_events|approvals)\.jsonl/i.test(String(command || ""));
}

function collectSection(lines: string[], section: string) {
  const result: string[] = [];
  let active = false;
  for (const line of lines) {
    if (/^#{1,4}\s+/.test(line) || /^\*\*[^*]+\*\*$/.test(line)) {
      const heading = cleanMarkdown(line).toLowerCase();
      if (active && heading !== section.toLowerCase()) break;
      active = heading === section.toLowerCase();
      continue;
    }
    if (active && /^[-*]\s+/.test(line)) result.push(cleanMarkdown(line));
  }
  return result;
}

function collectLikelySteps(lines: string[]) {
  const steps: string[] = [];
  for (const line of lines) {
    if (/^[-*]\s+/.test(line) && /(fix|add|run|test|build|verify|implement|新增|修|测试|验证|构建|运行|检查)/i.test(line)) {
      steps.push(cleanMarkdown(line));
    }
    if (/^\d+\.\s+/.test(line)) steps.push(cleanMarkdown(line));
  }
  return Array.from(new Set(steps));
}

function cleanMarkdown(line: string) {
  return line
    .replace(/^#{1,6}\s+/, "")
    .replace(/^[-*]\s+/, "")
    .replace(/^\d+\.\s+/, "")
    .replace(/^\*\*(.*?)\*\*$/, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

