export type ParsedPlanCard = {
  title: string;
  summary: string[];
  steps: string[];
  sections: ParsedPlanSection[];
  raw: string;
  isLong: boolean;
};

export type ParsedPlanSection = {
  title: string;
  body: string[];
  items: string[];
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
  const sections = collectPlanSections(lines, title);
  const summarySection = sections.find((section) => isSectionTitle(section.title, ["summary", "概要", "摘要"]));
  const summary = [...(summarySection?.body ?? []), ...(summarySection?.items ?? [])].slice(0, 5);
  const steps = collectLikelySteps(lines).slice(0, 8);
  return {
    title,
    summary: summary.length > 0 ? summary : lines.filter((line) => /^[-*]\s+/.test(line)).map(cleanMarkdown).slice(0, 4),
    steps,
    sections,
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

function collectPlanSections(lines: string[], title: string): ParsedPlanSection[] {
  const sections: ParsedPlanSection[] = [];
  let current: ParsedPlanSection | null = null;
  let skippedTitle = false;

  for (const line of lines) {
    const heading = extractSectionHeading(line);
    if (heading) {
      const cleanHeading = cleanMarkdown(heading);
      if (!skippedTitle && cleanHeading === title) {
        skippedTitle = true;
        current = null;
        continue;
      }
      current = { title: normalizeSectionTitle(cleanHeading), body: [], items: [] };
      sections.push(current);
      continue;
    }

    if (!current) continue;
    const cleaned = cleanPlanLine(line);
    if (!cleaned) continue;
    if (/^([-*+]\s+|\d+[.)]\s+)/.test(line)) {
      current.items.push(cleaned);
    } else {
      current.body.push(cleaned);
    }
  }

  return sections.filter((section) => section.body.length > 0 || section.items.length > 0);
}

function extractSectionHeading(line: string) {
  const markdownHeading = line.match(/^#{1,6}\s+(.+)$/);
  if (markdownHeading) return markdownHeading[1];
  const boldHeading = line.match(/^\*\*([^*]+)\*\*:?\s*$/);
  if (boldHeading) return boldHeading[1];
  const plain = line.replace(/[:：]\s*$/, "").trim();
  return isKnownSectionTitle(plain) ? plain : "";
}

function normalizeSectionTitle(title: string) {
  const trimmed = title.replace(/[:：]\s*$/, "").trim();
  const aliases: Record<string, string> = {
    summary: "Summary",
    "key changes": "Key Changes",
    changes: "Key Changes",
    "implementation steps": "Implementation Steps",
    steps: "Implementation Steps",
    "test plan": "Test Plan",
    tests: "Test Plan",
    assumptions: "Assumptions",
    risks: "Risks",
    "current progress": "Current Progress",
    "open questions": "Open Questions",
    概要: "概要",
    摘要: "摘要",
    关键变化: "关键变化",
    主要变更: "主要变更",
    实现步骤: "实现步骤",
    测试计划: "测试计划",
    验证计划: "验证计划",
    假设: "假设",
    风险: "风险",
    当前进度: "当前进度",
    待确认问题: "待确认问题",
  };
  return aliases[titleKey(trimmed)] ?? trimmed;
}

function isKnownSectionTitle(title: string) {
  return isSectionTitle(title, [
    "summary",
    "key changes",
    "changes",
    "implementation steps",
    "steps",
    "test plan",
    "tests",
    "assumptions",
    "risks",
    "current progress",
    "open questions",
    "概要",
    "摘要",
    "关键变化",
    "主要变更",
    "实现步骤",
    "测试计划",
    "验证计划",
    "假设",
    "风险",
    "当前进度",
    "待确认问题",
  ]);
}

function isSectionTitle(title: string, candidates: string[]) {
  const key = titleKey(title);
  return candidates.some((candidate) => titleKey(candidate) === key);
}

function titleKey(title: string) {
  return title.replace(/[:：]\s*$/, "").trim().toLowerCase();
}

function collectLikelySteps(lines: string[]) {
  const steps: string[] = [];
  for (const line of lines) {
    if (/^[-*]\s+/.test(line) && /(fix|add|run|test|build|verify|implement|新增|修复|测试|验证|构建|运行|检查)/i.test(line)) {
      steps.push(cleanPlanLine(line));
    }
    if (/^\d+\.\s+/.test(line)) steps.push(cleanPlanLine(line));
  }
  return Array.from(new Set(steps));
}

function cleanPlanLine(line: string) {
  return line
    .replace(/^#{1,6}\s+/, "")
    .replace(/^[-*+]\s+/, "")
    .replace(/^\d+[.)]\s+/, "")
    .replace(/^\*\*(.*?)\*\*:?\s*$/, "$1")
    .trim();
}

function cleanMarkdown(line: string) {
  return cleanPlanLine(line)
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}
