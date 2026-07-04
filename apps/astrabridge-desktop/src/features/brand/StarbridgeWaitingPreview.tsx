import { useEffect, useState } from "react";

import type { LocaleCode } from "../../types";
import { StarbridgeWaitingConstellation, type StarbridgeWaitingPhase } from "./StarbridgeWaitingConstellation";

type PreviewCopy = {
  shellEyebrow: string;
  title: string;
  summary: string;
  localeZh: string;
  localeEn: string;
  scenarios: string;
  phases: string;
  shortWait: string;
  mediumWait: string;
};

const PREVIEW_PHASES: StarbridgeWaitingPhase[] = ["thinking", "tools", "web", "files", "automation", "approval"];

const PHASE_COPY: Record<LocaleCode, Record<StarbridgeWaitingPhase, { label: string; title: string; detail: string }>> = {
  "zh-CN": {
    thinking: {
      label: "Thinking",
      title: "Thinking through the next move",
      detail: "The lane stays warm while the next command chain is prepared.",
    },
    tools: {
      label: "Tools",
      title: "Calling local tools",
      detail: "Commands, arguments, and results stay synchronized before the reply lands.",
    },
    web: {
      label: "Web",
      title: "Collecting fresh web evidence",
      detail: "Sources are gathered first and only then written back into the task stream.",
    },
    files: {
      label: "Files",
      title: "Editing project files",
      detail: "Diffs are still converging before the response is released to the user.",
    },
    automation: {
      label: "Automation",
      title: "Advancing automation",
      detail: "The executor and recovery signals keep moving without losing task context.",
    },
    approval: {
      label: "Approval",
      title: "Waiting for your approval",
      detail: "High-risk work stays paused until you explicitly confirm the next move.",
    },
  },
  en: {
    thinking: {
      label: "Thinking",
      title: "Thinking through the next move",
      detail: "The lane stays warm while the next command chain is prepared.",
    },
    tools: {
      label: "Tools",
      title: "Calling local tools",
      detail: "Commands, arguments, and results stay synchronized before the reply lands.",
    },
    web: {
      label: "Web",
      title: "Collecting fresh web evidence",
      detail: "Sources are gathered first and only then written back into the task stream.",
    },
    files: {
      label: "Files",
      title: "Editing project files",
      detail: "Diffs are still converging before the response is released to the user.",
    },
    automation: {
      label: "Automation",
      title: "Advancing automation",
      detail: "The executor and recovery signals keep moving without losing task context.",
    },
    approval: {
      label: "Approval",
      title: "Waiting for your approval",
      detail: "High-risk work stays paused until you explicitly confirm the next move.",
    },
  },
};

const PREVIEW_COPY: Record<LocaleCode, PreviewCopy> = {
  "zh-CN": {
    shellEyebrow: "Brand smoke preview",
    title: "Starbridge waiting-state primitive",
    summary: "Step 11 only builds the reusable primitive plus local state switching. Real runtime binding stays in Step 12.",
    localeZh: "ZH",
    localeEn: "English",
    scenarios: "Scenarios",
    phases: "Phases",
    shortWait: "Short wait",
    mediumWait: "Medium wait",
  },
  en: {
    shellEyebrow: "Brand smoke preview",
    title: "Starbridge waiting-state primitive",
    summary: "Step 11 only builds the reusable primitive plus local state switching. Real runtime binding stays in Step 12.",
    localeZh: "ZH",
    localeEn: "English",
    scenarios: "Scenarios",
    phases: "Phases",
    shortWait: "Short wait",
    mediumWait: "Medium wait",
  },
};

function queryValue(name: string) {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(name);
}

function initialLocale(): LocaleCode {
  const queryLocale = queryValue("locale");
  if (queryLocale === "zh-CN" || queryLocale === "en") {
    return queryLocale;
  }
  if (typeof navigator !== "undefined" && navigator.language.toLowerCase().startsWith("zh")) {
    return "zh-CN";
  }
  return "en";
}

function initialPhase(): StarbridgeWaitingPhase {
  const queryPhase = queryValue("waiting_phase");
  return PREVIEW_PHASES.includes(queryPhase as StarbridgeWaitingPhase) ? (queryPhase as StarbridgeWaitingPhase) : "thinking";
}

export function StarbridgeWaitingPreview() {
  const [locale, setLocale] = useState<LocaleCode>(() => initialLocale());
  const [phase, setPhase] = useState<StarbridgeWaitingPhase>(() => initialPhase());
  const copy = PREVIEW_COPY[locale];
  const phaseCopy = PHASE_COPY[locale][phase];

  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    url.searchParams.set("brand_waiting_preview", "1");
    url.searchParams.set("waiting_phase", phase);
    url.searchParams.set("locale", locale);
    window.history.replaceState(null, "", url);
  }, [locale, phase]);

  return (
    <main className="brand-waiting-preview-shell" data-testid="brand-waiting-preview">
      <section className="brand-waiting-preview-head">
        <div className="brand-waiting-preview-copy">
          <span className="eyebrow">{copy.shellEyebrow}</span>
          <h1>{copy.title}</h1>
          <p>{copy.summary}</p>
        </div>
        <div className="brand-waiting-preview-controls" aria-label={copy.scenarios}>
          <div className="brand-waiting-preview-control-group">
            <span>{copy.phases}</span>
            <div className="segmented segmented-wrap">
              {PREVIEW_PHASES.map((item) => (
                <button key={item} type="button" className={phase === item ? "segmented-active" : ""} onClick={() => setPhase(item)}>
                  {PHASE_COPY[locale][item].label}
                </button>
              ))}
            </div>
          </div>
          <div className="brand-waiting-preview-control-group">
            <span>Locale</span>
            <div className="segmented">
              <button type="button" className={locale === "zh-CN" ? "segmented-active" : ""} onClick={() => setLocale("zh-CN")}>
                {copy.localeZh}
              </button>
              <button type="button" className={locale === "en" ? "segmented-active" : ""} onClick={() => setLocale("en")}>
                {copy.localeEn}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="brand-waiting-preview-band">
        <div className="brand-waiting-preview-band-head">
          <span>{copy.shortWait}</span>
          <strong>{phaseCopy.label}</strong>
        </div>
        <StarbridgeWaitingConstellation variant="inline" phase={phase} title={phaseCopy.title} detail={phaseCopy.detail} />
      </section>

      <section className="brand-waiting-preview-stage">
        <div className="brand-waiting-preview-band-head">
          <span>{copy.mediumWait}</span>
          <strong>{phaseCopy.label}</strong>
        </div>
        <StarbridgeWaitingConstellation variant="panel" phase={phase} label={phaseCopy.label} title={phaseCopy.title} detail={phaseCopy.detail} />
      </section>
    </main>
  );
}
