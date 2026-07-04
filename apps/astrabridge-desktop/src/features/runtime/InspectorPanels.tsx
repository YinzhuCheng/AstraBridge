import { ArrowLeft, ArrowRight, ChevronDown, ChevronUp, ExternalLink, Files, Grid2X2, RefreshCw, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { StarbridgeBrowserIcon, StarbridgeFilesIcon, StarbridgeReviewIcon, StarbridgeStatusIcon } from "../brand/StarbridgeIcons";
import type { FormEvent, MouseEvent, ReactNode, WheelEvent } from "react";
import { api, projectFileMediaHref } from "../../api";
import { t } from "../i18n/catalog";
import type {
  BrowserWorkbenchSession,
  ComputerUseBrowserScenarioReport,
  ProjectFile,
  ProjectFilePreview,
  ProjectFilesTree,
  ProjectReviewDiff,
  ProjectReviewFile,
  ProjectReviewStatus,
  RuntimeSupervisorState,
} from "../../types";
import type { CodingEventInspectorSummary } from "./codingEventInspector";
import type { TaskWorkflowFacts } from "./taskWorkflowFacts";

export type InspectorTab = "status" | "review" | "browser" | "files";

type Locale = "en" | "zh-CN";

type BrowserSmokeSummary = {
  label?: string;
  status?: string;
  url?: string;
  console_errors?: string[];
  request_failures?: Array<{ url?: string; method?: string; resource_type?: string; error_text?: string }>;
  screenshot_path?: string;
} | null;

function normalizeBrowserUrl(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return "about:blank";
  if (/^(https?:|file:|about:)/i.test(trimmed)) return trimmed;
  if (/^(localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(\/|$)/i.test(trimmed)) {
    return `http://${trimmed}`;
  }
  return `https://${trimmed}`;
}

function normalizeManagedBrowserUrl(value: string) {
  const normalized = normalizeBrowserUrl(value);
  const parsed = new URL(normalized);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Only http and https URLs are supported.");
  }
  return parsed.toString();
}

function roleFromUrl(url: string) {
  try {
    const host = new URL(url).hostname.replace(/^www\./, "");
    if (!host) return "Browser";
    const name = host.split(".")[0] || host;
    return name.slice(0, 1).toUpperCase() + name.slice(1);
  } catch {
    return "Browser";
  }
}

function isSelfPreviewUrl(value: string) {
  if (typeof window === "undefined") return false;
  try {
    const target = new URL(value);
    const current = new URL(window.location.href);
    return target.origin === current.origin;
  } catch {
    return false;
  }
}

function compactPathLabel(path: string | null | undefined) {
  const value = String(path || "").trim();
  if (!value) return "";
  const parts = value.split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 2) return value;
  return parts.slice(-2).join("/");
}

function fileNameLabel(path: string | null | undefined) {
  const value = String(path || "").trim();
  if (!value) return "";
  const parts = value.split(/[\\/]+/).filter(Boolean);
  return parts[parts.length - 1] || value;
}

function compactStatusCode(status: string | null | undefined) {
  const value = String(status || "").trim().toLowerCase();
  if (!value) return "-";
  if (value.startsWith("mod")) return "M";
  if (value.startsWith("add")) return "+";
  if (value.startsWith("del")) return "-";
  if (value.startsWith("ren")) return "R";
  if (value.startsWith("cop")) return "C";
  return value.slice(0, 1).toUpperCase();
}

function parentPathLabel(path: string | null | undefined) {
  const value = String(path || "").trim();
  if (!value) return "";
  const parts = value.split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 1) return "";
  return parts.slice(Math.max(0, parts.length - 3), -1).join("/");
}

function compactUrlLabel(value: string | null | undefined) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const url = new URL(raw);
    const path = url.pathname === "/" ? "" : url.pathname.replace(/\/+$/, "");
    const compactPath = path.length > 18 ? `${path.slice(0, 18)}…` : path;
    return `${url.host}${compactPath}`;
  } catch {
    return raw.length > 32 ? `${raw.slice(0, 32)}…` : raw;
  }
}

const BROWSER_MOBILE_ASPECT_THRESHOLD = 1.28;
function browserEffectiveHost(value: string | null | undefined) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    return new URL(raw).host.replace(/^www\./i, "");
  } catch {
    return raw;
  }
}

function isLoopbackBrowserHost(hostname: string) {
  const host = hostname.toLowerCase();
  return host === "localhost" || host === "127.0.0.1" || host === "::1" || host === "[::1]" || host.endsWith(".localhost");
}

function browserLiveFrameUrl(session: BrowserWorkbenchSession | null) {
  if (!session || session.preview_mode !== "remote") return "";
  const raw = String(session.url || "").trim();
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    const host = parsed.hostname.toLowerCase();
    if (isLoopbackBrowserHost(host)) return parsed.toString();
    if (host === "example.com" || host === "www.example.com" || host === "example.org" || host === "www.iana.org") {
      return parsed.toString();
    }
    if (/\.wikipedia\.org$/i.test(host)) return parsed.toString();
    if ((host === "google.com" || host === "www.google.com") && parsed.searchParams.get("igu") === "1") {
      return parsed.toString();
    }
  } catch {
    return "";
  }
  return "";
}

const BROWSER_TWO_PAGE_ASPECT_THRESHOLD = 2.14;
const BROWSER_TWO_PAGE_MAX_FIT_SCORE = 60;

export function browserStageAspectRatio(width: number, height: number) {
  const normalizedWidth = Math.max(0, Math.round(width || 0));
  const normalizedHeight = Math.max(0, Math.round(height || 0));
  if (!normalizedWidth || !normalizedHeight) return 0;
  return normalizedHeight / normalizedWidth;
}

export function desiredBrowserLayoutMode({
  isRemote,
  width,
  height,
}: {
  isRemote: boolean;
  width: number;
  height: number;
}): "desktop" | "mobile" {
  if (!isRemote) return "desktop";
  return browserStageAspectRatio(width, height) >= BROWSER_MOBILE_ASPECT_THRESHOLD ? "mobile" : "desktop";
}

export function shouldUseBrowserTwoPageStack({
  isRemote,
  desiredMode,
  aspect,
  mobileOptimized,
  responsiveFitScore,
  hasPeer,
}: {
  isRemote: boolean;
  desiredMode: "desktop" | "mobile";
  aspect: number;
  mobileOptimized?: boolean | null;
  responsiveFitScore?: number | null;
  hasPeer: boolean;
}) {
  const fitScore = typeof responsiveFitScore === "number" ? responsiveFitScore : null;
  return (
    isRemote &&
    desiredMode === "mobile" &&
    aspect >= BROWSER_TWO_PAGE_ASPECT_THRESHOLD &&
    mobileOptimized === false &&
    (fitScore == null || fitScore <= BROWSER_TWO_PAGE_MAX_FIT_SCORE) &&
    hasPeer
  );
}

function workbenchStatusLabel(locale: Locale, status: string) {
  if (status === "open") return t(locale, "browser_workbench_status_open");
  if (status === "focused") return t(locale, "browser_workbench_status_focused");
  if (status === "web_fallback") return t(locale, "browser_workbench_status_fallback");
  if (status === "navigating") return locale === "zh-CN" ? "正在载入" : "Loading";
  if (status === "error") return locale === "zh-CN" ? "异常" : "Error";
  if (status === "idle") return locale === "zh-CN" ? "空闲" : "Idle";
  if (status === "closed") return locale === "zh-CN" ? "已关闭" : "Closed";
  return status || "-";
}

function browserRoleLabel(locale: Locale, role: string) {
  const normalized = role.trim().toLowerCase();
  if (locale === "zh-CN" && normalized === "news") return "新闻";
  return role || "Browser";
}

function browserUrlChromeLabel(value: string | null | undefined) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const url = new URL(raw);
    const path = url.pathname === "/" ? "" : url.pathname.replace(/\/+$/, "");
    const compactPath = path.length > 18 ? `${path.slice(0, 18)}...` : path;
    return `${url.host}${compactPath}`;
  } catch {
    return raw.length > 32 ? `${raw.slice(0, 32)}...` : raw;
  }
}

function browserStatusText(locale: Locale, status: string) {
  if (status === "open") return t(locale, "browser_workbench_status_open");
  if (status === "focused") return t(locale, "browser_workbench_status_focused");
  if (status === "web_fallback") return t(locale, "browser_workbench_status_fallback");
  if (status === "navigating") return locale === "zh-CN" ? "载入中" : "Loading";
  if (status === "error") return locale === "zh-CN" ? "异常" : "Error";
  if (status === "idle") return locale === "zh-CN" ? "空闲" : "Idle";
  if (status === "closed") return locale === "zh-CN" ? "已关闭" : "Closed";
  return status || "-";
}

function browserRoleText(locale: Locale, role: string) {
  const normalized = role.trim().toLowerCase();
  if (locale === "zh-CN" && normalized === "news") return "新闻";
  return role || "Browser";
}

function browserMobileStrategyText(locale: Locale, strategy: string | null | undefined) {
  const normalized = String(strategy || "").trim().toLowerCase();
  if (normalized === "mobile_host_rewrite_viewport") return locale === "zh-CN" ? "手机渲染 · m 站入口" : "Phone render · m-site";
  if (normalized === "mobile_user_agent_viewport") return locale === "zh-CN" ? "手机渲染 · 响应式入口" : "Phone render · responsive";
  if (normalized === "desktop_viewport") return locale === "zh-CN" ? "桌面视口" : "Desktop viewport";
  return normalized || (locale === "zh-CN" ? "浏览器渲染" : "Browser render");
}

function browserTabLine(locale: Locale, session: BrowserWorkbenchSession) {
  const pageTitle = String(session.page_title || "").trim();
  if (pageTitle) return pageTitle;
  const role = browserRoleText(locale, session.role);
  const chrome = browserUrlChromeLabel(session.url);
  return chrome && chrome.toLowerCase() !== role.toLowerCase() ? `${role} · ${chrome}` : role;
}

function browserMobileSurfaceTitle(locale: Locale, session: BrowserWorkbenchSession | null, stackMode: boolean) {
  if (!session) return "";
  const strategy = browserMobileStrategyText(locale, session.mobile_strategy || session.layout_mode || "desktop");
  const fit = typeof session.responsive_fit_score === "number" ? ` fit ${session.responsive_fit_score}` : "";
  if (locale === "zh-CN") {
    return stackMode
      ? `移动渲染未完全贴合，已启用双页瘦高视图；${strategy}${fit}`
      : `托管浏览器画面；${strategy}${fit}`;
  }
  return stackMode
    ? `Mobile rendering did not fit cleanly; two-page tall view is enabled; ${strategy}${fit}`
    : `Managed browser surface; ${strategy}${fit}`;
}

function browserTabTitle(locale: Locale, session: BrowserWorkbenchSession) {
  const pageTitle = String(session.page_title || "").trim();
  if (pageTitle) return pageTitle;
  return browserRoleText(locale, session.role);
}

type BrowserRenderSummary = {
  detail: string;
  mode: string;
  title: string;
  tone: "desktop" | "mobile" | "native" | "stack";
};

function browserRenderSummary(
  locale: Locale,
  session: BrowserWorkbenchSession | null,
  options: { desiredMode: "desktop" | "mobile"; stackMode: boolean },
): BrowserRenderSummary | null {
  if (!session) return null;
  const host = browserUrlChromeLabel(session.url);
  const fit = typeof session.responsive_fit_score === "number" ? Math.round(session.responsive_fit_score) : null;
  const fitLabel = fit == null ? "" : locale === "zh-CN" ? `贴合 ${fit}` : `fit ${fit}`;
  const viewportLabel = session.has_viewport_meta === true
    ? locale === "zh-CN" ? "含 viewport meta" : "viewport meta"
    : session.has_viewport_meta === false
      ? locale === "zh-CN" ? "无 viewport meta" : "no viewport meta"
      : "";
  const extra = [host, fitLabel, viewportLabel].filter(Boolean).join(" · ");
  const currentMode = String(session.layout_mode || options.desiredMode || "desktop").toLowerCase();

  if (session.preview_mode === "native") {
    return {
      tone: "native",
      mode: locale === "zh-CN" ? "前台窗口" : "Foreground window",
      detail: locale === "zh-CN" ? "WebView2 监督" : "WebView2 supervision",
      title: [locale === "zh-CN"
        ? "Google、YouTube 这类禁止 iframe 的站点会在前台 WebView2 窗口中运行。"
        : "Sites that block iframe embedding run in a foreground WebView2 window.", extra].filter(Boolean).join(" "),
    };
  }

  if (options.stackMode) {
    return {
      tone: "stack",
      mode: locale === "zh-CN" ? "双页长视图" : "Two-page tall view",
      detail: locale === "zh-CN" ? "保留双页兜底" : "Two-page fallback",
      title: [locale === "zh-CN"
        ? "当右侧栏过于瘦高且站点不够移动端友好时，星桥会保留双页长视图。"
        : "When the right pane is very tall and the site is not mobile-friendly enough, AstraBridge keeps a two-page tall view.", extra].filter(Boolean).join(" "),
    };
  }

  if (currentMode === "mobile") {
    if (String(session.mobile_strategy || "").toLowerCase() === "mobile_host_rewrite_viewport") {
      return {
        tone: "mobile",
        mode: locale === "zh-CN" ? "手机入口" : "Mobile entry",
        detail: locale === "zh-CN" ? "m 站入口" : "m-site entry",
        title: [locale === "zh-CN"
          ? "先命中已知移动端入口；如果站点没有独立入口，再退回响应式窄屏渲染。"
          : "AstraBridge tries a known mobile entry host first, then falls back to responsive narrow rendering.", extra].filter(Boolean).join(" "),
      };
    }
    return {
      tone: "mobile",
      mode: locale === "zh-CN" ? "响应式窄屏" : "Responsive narrow view",
      detail: locale === "zh-CN" ? "手机视口" : "Phone viewport",
      title: [locale === "zh-CN"
        ? "站点没有独立移动域名时，星桥会改用手机视口和窄栏渲染。"
        : "If no dedicated mobile host exists, AstraBridge uses a mobile viewport inside the narrow pane.", extra].filter(Boolean).join(" "),
    };
  }

  return {
    tone: "desktop",
    mode: locale === "zh-CN" ? "桌面视口" : "Desktop viewport",
    detail: locale === "zh-CN" ? "当前宽度更适合桌面布局" : "Current pane width favors the desktop layout",
    title: [locale === "zh-CN"
      ? "当前面板宽度足以维持桌面布局。"
      : "The current pane width is wide enough to keep the desktop layout.", extra].filter(Boolean).join(" "),
  };
}

function browserStatusTextClean(locale: Locale, status: string) {
  if (status === "open") return t(locale, "browser_workbench_status_open");
  if (status === "focused") return t(locale, "browser_workbench_status_focused");
  if (status === "web_fallback") return t(locale, "browser_workbench_status_fallback");
  if (status === "navigating") return locale === "zh-CN" ? "加载中" : "Loading";
  if (status === "error") return locale === "zh-CN" ? "异常" : "Error";
  if (status === "idle") return locale === "zh-CN" ? "空闲" : "Idle";
  if (status === "closed") return locale === "zh-CN" ? "已关闭" : "Closed";
  return status || "-";
}

function browserRoleTextClean(locale: Locale, role: string) {
  const normalized = role.trim().toLowerCase();
  if (locale === "zh-CN" && normalized === "news") return "新闻";
  return role || "Browser";
}

function browserMobileStrategyTextClean(locale: Locale, strategy: string | null | undefined) {
  const normalized = String(strategy || "").trim().toLowerCase();
  if (normalized === "mobile_host_rewrite_viewport") return locale === "zh-CN" ? "手机渲染 | 移动入口" : "Phone render | mobile entry";
  if (normalized === "mobile_user_agent_viewport") return locale === "zh-CN" ? "手机渲染 | 响应式" : "Phone render | responsive";
  if (normalized === "desktop_viewport") return locale === "zh-CN" ? "桌面视口" : "Desktop viewport";
  return normalized || (locale === "zh-CN" ? "浏览器渲染" : "Browser render");
}

function browserTabLineClean(locale: Locale, session: BrowserWorkbenchSession) {
  const pageTitle = String(session.page_title || "").trim();
  const chrome = browserUrlChromeLabel(session.url);
  if (pageTitle && chrome && pageTitle.toLowerCase() !== chrome.toLowerCase()) return pageTitle;
  if (chrome) return chrome;
  return browserRoleTextClean(locale, session.role);
}

function browserMobileSurfaceTitleClean(locale: Locale, session: BrowserWorkbenchSession | null, stackMode: boolean) {
  if (!session) return "";
  const strategy = browserMobileStrategyTextClean(locale, session.mobile_strategy || session.layout_mode || "desktop");
  const fit = typeof session.responsive_fit_score === "number" ? ` fit ${session.responsive_fit_score}` : "";
  if (locale === "zh-CN") {
    return stackMode
      ? `当前站点在瘦高面板下仍不够适合单页移动渲染，已切换到双页纵向视图；${strategy}${fit}`
      : `托管浏览器快照；${strategy}${fit}`;
  }
  return stackMode
    ? `Mobile rendering did not fit cleanly; two-page tall view is enabled; ${strategy}${fit}`
    : `Managed browser surface; ${strategy}${fit}`;
}

function browserRenderSummaryClean(
  locale: Locale,
  session: BrowserWorkbenchSession | null,
  options: { desiredMode: "desktop" | "mobile"; stackMode: boolean },
): BrowserRenderSummary | null {
  if (!session) return null;
  const host = browserUrlChromeLabel(session.url);
  const effectiveHost = browserEffectiveHost(session.url);
  const fit = typeof session.responsive_fit_score === "number" ? Math.round(session.responsive_fit_score) : null;
  const fitLabel = fit == null ? "" : locale === "zh-CN" ? `贴合 ${fit}` : `fit ${fit}`;
  const viewportLabel = session.has_viewport_meta === true
    ? locale === "zh-CN" ? "含 viewport meta" : "viewport meta"
    : session.has_viewport_meta === false
      ? locale === "zh-CN" ? "无 viewport meta" : "no viewport meta"
      : "";
  const extra = [host, fitLabel, viewportLabel].filter(Boolean).join(" | ");
  const currentMode = String(session.layout_mode || options.desiredMode || "desktop").toLowerCase();

  if (session.preview_mode === "native") {
    return {
      tone: "native",
      mode: locale === "zh-CN" ? "前台窗口" : "Foreground window",
      detail: locale === "zh-CN" ? "WebView2 监督" : "WebView2 supervision",
      title: [
        locale === "zh-CN"
          ? "像 Google、YouTube 这类阻止 iframe 嵌入的网站，会在前台 WebView2 窗口中运行。"
          : "Sites that block iframe embedding run in a foreground WebView2 window.",
        extra,
      ].filter(Boolean).join(" "),
    };
  }

  if (options.stackMode) {
    return {
      tone: "stack",
      mode: locale === "zh-CN" ? "双页纵向" : "Two-page tall view",
      detail: effectiveHost || (locale === "zh-CN" ? "双页兜底" : "Two-page fallback"),
      title: [
        locale === "zh-CN"
          ? "当右侧面板过于瘦高、且站点不够适合单页移动渲染时，星桥会保留双页纵向视图。"
          : "When the right pane is very tall and the site is not mobile-friendly enough, AstraBridge keeps a two-page tall view.",
        extra,
      ].filter(Boolean).join(" "),
    };
  }

  if (currentMode === "mobile") {
    if (String(session.mobile_strategy || "").toLowerCase() === "mobile_host_rewrite_viewport") {
      return {
        tone: "mobile",
        mode: locale === "zh-CN" ? "移动入口" : "Mobile entry",
        detail: effectiveHost || (locale === "zh-CN" ? "已切到移动站点" : "mobile host"),
        title: [
          locale === "zh-CN"
            ? "星桥优先尝试已知的移动端入口；如果站点没有独立移动入口，再退回响应式窄屏渲染。"
            : "AstraBridge tries a known mobile entry host first, then falls back to responsive narrow rendering.",
          extra,
        ].filter(Boolean).join(" "),
      };
    }
    return {
      tone: "mobile",
      mode: locale === "zh-CN" ? "响应式窄屏" : "Responsive narrow view",
      detail: effectiveHost || (locale === "zh-CN" ? "手机视口" : "Phone viewport"),
      title: [
        locale === "zh-CN"
          ? "如果站点没有独立移动域名，星桥会在窄栏里使用手机视口和移动 UA。"
          : "If no dedicated mobile host exists, AstraBridge uses a mobile viewport inside the narrow pane.",
        extra,
      ].filter(Boolean).join(" "),
    };
  }

  return {
    tone: "desktop",
    mode: locale === "zh-CN" ? "桌面视口" : "Desktop viewport",
    detail: locale === "zh-CN" ? "当前宽度适合桌面布局" : "Current pane width favors the desktop layout",
    title: [
      locale === "zh-CN" ? "当前面板宽度足以维持桌面布局。" : "The current pane width is wide enough to keep the desktop layout.",
      extra,
    ].filter(Boolean).join(" "),
  };
}

function browserStatusTextBrand(locale: Locale, status: string) {
  if (status === "open") return t(locale, "browser_workbench_status_open");
  if (status === "focused") return t(locale, "browser_workbench_status_focused");
  if (status === "web_fallback") return t(locale, "browser_workbench_status_fallback");
  if (status === "navigating") return locale === "zh-CN" ? "加载中" : "Loading";
  if (status === "error") return locale === "zh-CN" ? "异常" : "Error";
  if (status === "idle") return locale === "zh-CN" ? "空闲" : "Idle";
  if (status === "closed") return locale === "zh-CN" ? "已关闭" : "Closed";
  return status || "-";
}

function browserRoleTextBrand(locale: Locale, role: string) {
  const normalized = role.trim().toLowerCase();
  if (locale === "zh-CN" && normalized === "news") return "新闻";
  return role || "Browser";
}

function browserMobileStrategyTextBrand(locale: Locale, strategy: string | null | undefined) {
  const normalized = String(strategy || "").trim().toLowerCase();
  if (normalized === "mobile_host_rewrite_viewport") return locale === "zh-CN" ? "手机渲染 | 移动入口" : "Phone render | mobile entry";
  if (normalized === "mobile_user_agent_viewport") return locale === "zh-CN" ? "手机渲染 | 响应式" : "Phone render | responsive";
  if (normalized === "desktop_viewport") return locale === "zh-CN" ? "桌面视口" : "Desktop viewport";
  return normalized || (locale === "zh-CN" ? "浏览器渲染" : "Browser render");
}

function browserTabLineBrand(locale: Locale, session: BrowserWorkbenchSession) {
  const pageTitle = String(session.page_title || "").trim();
  const chrome = browserUrlChromeLabel(session.url);
  if (pageTitle && chrome && pageTitle.toLowerCase() !== chrome.toLowerCase()) return pageTitle;
  if (chrome) return chrome;
  return browserRoleTextBrand(locale, session.role);
}

function browserMobileSurfaceTitleBrand(locale: Locale, session: BrowserWorkbenchSession | null, stackMode: boolean) {
  if (!session) return "";
  const strategy = browserMobileStrategyTextBrand(locale, session.mobile_strategy || session.layout_mode || "desktop");
  const fit = typeof session.responsive_fit_score === "number" ? ` fit ${session.responsive_fit_score}` : "";
  if (locale === "zh-CN") {
    return stackMode
      ? `当前站点在瘦高面板下仍不适合单页移动渲染，已切换到双页纵向视图；${strategy}${fit}`
      : `托管浏览器快照；${strategy}${fit}`;
  }
  return stackMode
    ? `Mobile rendering did not fit cleanly; two-page tall view is enabled; ${strategy}${fit}`
    : `Managed browser surface; ${strategy}${fit}`;
}

function browserRenderSummaryBrand(
  locale: Locale,
  session: BrowserWorkbenchSession | null,
  options: { desiredMode: "desktop" | "mobile"; stackMode: boolean },
): BrowserRenderSummary | null {
  if (!session) return null;
  const host = browserUrlChromeLabel(session.url);
  const effectiveHost = browserEffectiveHost(session.url);
  const fit = typeof session.responsive_fit_score === "number" ? Math.round(session.responsive_fit_score) : null;
  const fitLabel = fit == null ? "" : locale === "zh-CN" ? `贴合 ${fit}` : `fit ${fit}`;
  const viewportLabel = session.has_viewport_meta === true
    ? (locale === "zh-CN" ? "含 viewport meta" : "viewport meta")
    : session.has_viewport_meta === false
      ? (locale === "zh-CN" ? "无 viewport meta" : "no viewport meta")
      : "";
  const extra = [host, fitLabel, viewportLabel].filter(Boolean).join(" | ");
  const currentMode = String(session.layout_mode || options.desiredMode || "desktop").toLowerCase();

  if (session.preview_mode === "native") {
    return {
      tone: "native",
      mode: locale === "zh-CN" ? "前台窗口" : "Foreground window",
      detail: locale === "zh-CN" ? "WebView2 监督" : "WebView2 supervision",
      title: [
        locale === "zh-CN"
          ? "像 Google、YouTube 这类阻止 iframe 嵌入的网站，会在前台 WebView2 窗口中运行。"
          : "Sites that block iframe embedding run in a foreground WebView2 window.",
        extra,
      ].filter(Boolean).join(" "),
    };
  }

  if (options.stackMode) {
    return {
      tone: "stack",
      mode: locale === "zh-CN" ? "双页纵向" : "Two-page tall view",
      detail: effectiveHost || (locale === "zh-CN" ? "保留双页兜底" : "Two-page fallback"),
      title: [
        locale === "zh-CN"
          ? "当右侧面板过于瘦高、且站点不够适合单页移动渲染时，星桥会保留双页纵向视图。"
          : "When the right pane is very tall and the site is not mobile-friendly enough, AstraBridge keeps a two-page tall view.",
        extra,
      ].filter(Boolean).join(" "),
    };
  }

  if (currentMode === "mobile") {
    if (String(session.mobile_strategy || "").toLowerCase() === "mobile_host_rewrite_viewport") {
      return {
        tone: "mobile",
        mode: locale === "zh-CN" ? "手机入口" : "Mobile entry",
        detail: effectiveHost || (locale === "zh-CN" ? "已切到移动站点" : "mobile host"),
        title: [
          locale === "zh-CN"
            ? "星桥优先尝试已知的移动端入口；如果站点没有独立移动入口，再退回响应式窄屏渲染。"
            : "AstraBridge tries a known mobile entry host first, then falls back to responsive narrow rendering.",
          extra,
        ].filter(Boolean).join(" "),
      };
    }
    return {
      tone: "mobile",
      mode: locale === "zh-CN" ? "响应式窄屏" : "Responsive narrow view",
      detail: effectiveHost || (locale === "zh-CN" ? "手机视口" : "Phone viewport"),
      title: [
        locale === "zh-CN"
          ? "如果站点没有独立移动域名，星桥会在窄栏里使用手机视口和移动 UA。"
          : "If no dedicated mobile host exists, AstraBridge uses a mobile viewport inside the narrow pane.",
        extra,
      ].filter(Boolean).join(" "),
    };
  }

  return {
    tone: "desktop",
    mode: locale === "zh-CN" ? "桌面视口" : "Desktop viewport",
    detail: locale === "zh-CN" ? "当前宽度更适合桌面布局" : "Current pane width favors the desktop layout",
    title: [
      locale === "zh-CN" ? "当前面板宽度足以维持桌面布局。" : "The current pane width is wide enough to keep the desktop layout.",
      extra,
    ].filter(Boolean).join(" "),
  };
}

function reportStatusLabel(locale: Locale, status: string) {
  if (status === "model_runner_cua_observed") return t(locale, "browser_workbench_report_cua_observed");
  if (status === "model_runner_attempted") return t(locale, "browser_workbench_report_attempted");
  if (status === "model_runner_blocked") return t(locale, "browser_workbench_report_blocked");
  if (status === "prepared_for_computer_use") return t(locale, "browser_workbench_report_ready");
  if (status === "validated_with_limitations") return t(locale, "browser_workbench_report_limited");
  if (status === "prepared_with_plugin_probe_error") return t(locale, "browser_workbench_report_probe_error");
  if (status === "prepared") return t(locale, "browser_workbench_report_ready");
  return status || "-";
}

function attemptDisplayName(locale: Locale, attemptId: string) {
  if (attemptId === "current-model") return t(locale, "browser_workbench_attempt_current");
  if (attemptId === "yunwu-gpt-5.5") return "yunwu/gpt-5.5";
  return attemptId || "-";
}

function attemptStatusLabel(locale: Locale, status: string) {
  if (status === "cua_event_observed") return t(locale, "browser_workbench_attempt_cua_observed");
  if (status === "tool_event_observed") return t(locale, "browser_workbench_attempt_tool_observed");
  if (status === "completed_without_cua_event") return t(locale, "browser_workbench_attempt_completed_no_cua");
  if (status === "turn_started_no_cua_event_yet") return t(locale, "browser_workbench_attempt_started");
  if (status === "blocked_by_non_cua_request") return t(locale, "browser_workbench_attempt_blocked_request");
  if (status === "blocked") return t(locale, "browser_workbench_attempt_blocked");
  if (status === "queued_for_app_model_runner") return t(locale, "browser_workbench_attempt_queued");
  return status || "-";
}

function attemptBlockerLabel(locale: Locale, item: Record<string, unknown>) {
  const keyInjection = item.key_injection && typeof item.key_injection === "object" ? item.key_injection as Record<string, unknown> : null;
  const injectionReason = String(keyInjection?.reason ?? "");
  const failureReason = String(item.failure_reason ?? "");
  if (injectionReason === "not_managed") return t(locale, "browser_workbench_attempt_key_not_managed");
  if (injectionReason === "no_key") return t(locale, "browser_workbench_attempt_key_missing");
  if (failureReason.includes("runtime_secret_missing")) return t(locale, "browser_workbench_attempt_key_missing");
  if (failureReason) return failureReason.slice(0, 120);
  return "";
}

function reportModelStatus(locale: Locale, report: ComputerUseBrowserScenarioReport) {
  const attempts = report.attempts ?? [];
  if (!attempts.length) return t(locale, "browser_workbench_report_ready_detail");
  const parts = attempts.map((item) => {
    const attemptId = String(item.attempt_id ?? "");
    const status = String(item.status ?? "");
    const blocker = status === "blocked" || status === "blocked_by_non_cua_request" ? attemptBlockerLabel(locale, item) : "";
    return `${attemptDisplayName(locale, attemptId)}: ${attemptStatusLabel(locale, status)}${blocker ? ` (${blocker})` : ""}`;
  });
  return `${t(locale, "browser_workbench_model_runner_summary")} ${parts.join(" / ")}`;
}

function formatBytes(value: number | null | undefined) {
  const size = Number(value || 0);
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(size >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
}

function fileKindLabel(locale: Locale, kind: string | null | undefined) {
  const labels: Record<string, { en: string; zh: string }> = {
    markdown: { en: "Markdown", zh: "Markdown" },
    json: { en: "JSON", zh: "JSON" },
    text: { en: "Text", zh: "文本" },
    image: { en: "Image", zh: "图片" },
    pdf: { en: "PDF", zh: "PDF" },
    audio: { en: "Audio", zh: "音频" },
    video: { en: "Video", zh: "视频" },
    binary: { en: "Binary", zh: "二进制" },
    too_large: { en: "Too large", zh: "过大" },
  };
  const fallback = kind || "-";
  const entry = labels[fallback];
  return entry ? (locale === "zh-CN" ? entry.zh : entry.en) : fallback;
}

function filePanelText(locale: Locale, key: "current" | "files" | "preview" | "workspace" | "openRaw" | "loading" | "truncated" | "eventSummary") {
  const zh: Record<typeof key, string> = {
    current: "当前",
    files: "文件",
    preview: "预览",
    workspace: "工作区",
    openRaw: "打开原文件",
    loading: "正在加载预览...",
    truncated: "列表已截断",
    eventSummary: "事件摘要",
  };
  const en: Record<typeof key, string> = {
    current: "Current",
    files: "files",
    preview: "Preview",
    workspace: "Workspace",
    openRaw: "Open raw",
    loading: "Loading preview...",
    truncated: "List truncated",
    eventSummary: "event summary",
  };
  return locale === "zh-CN" ? zh[key] : en[key];
}

function renderMarkdownPreview(content: string) {
  const blocks: ReactNode[] = [];
  const lines = content.split(/\r?\n/);
  let codeLines: string[] = [];
  let listLines: string[] = [];
  let paragraph: string[] = [];
  let inCode = false;

  function flushParagraph(key: string) {
    if (!paragraph.length) return;
    blocks.push(<p key={key}>{paragraph.join(" ")}</p>);
    paragraph = [];
  }

  function flushList(key: string) {
    if (!listLines.length) return;
    blocks.push(
      <ul key={key}>
        {listLines.map((line, index) => (
          <li key={`${key}-${index}`}>{line}</li>
        ))}
      </ul>,
    );
    listLines = [];
  }

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      if (inCode) {
        blocks.push(
          <pre className="markdown-code" key={`code-${index}`}>
            {codeLines.join("\n")}
          </pre>,
        );
        codeLines = [];
        inCode = false;
      } else {
        flushParagraph(`p-${index}`);
        flushList(`ul-${index}`);
        inCode = true;
      }
      return;
    }
    if (inCode) {
      codeLines.push(line);
      return;
    }
    if (!trimmed) {
      flushParagraph(`p-${index}`);
      flushList(`ul-${index}`);
      return;
    }
    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushParagraph(`p-${index}`);
      flushList(`ul-${index}`);
      const level = heading[1].length;
      const text = heading[2];
      blocks.push(level === 1 ? <h3 key={`h-${index}`}>{text}</h3> : level === 2 ? <h4 key={`h-${index}`}>{text}</h4> : <h5 key={`h-${index}`}>{text}</h5>);
      return;
    }
    const bullet = /^[-*]\s+(.+)$/.exec(trimmed);
    if (bullet) {
      flushParagraph(`p-${index}`);
      listLines.push(bullet[1]);
      return;
    }
    if (trimmed.startsWith(">")) {
      flushParagraph(`p-${index}`);
      flushList(`ul-${index}`);
      blocks.push(<blockquote key={`q-${index}`}>{trimmed.replace(/^>\s?/, "")}</blockquote>);
      return;
    }
    paragraph.push(trimmed);
  });
  if (inCode) {
    blocks.push(
      <pre className="markdown-code" key="code-tail">
        {codeLines.join("\n")}
      </pre>,
    );
  }
  flushParagraph("p-tail");
  flushList("ul-tail");
  return blocks.length ? blocks : <p className="muted compact-copy">{content}</p>;
}

function prettyText(kind: string | undefined, content: string | undefined) {
  if (!content) return "";
  if (kind !== "json") return content;
  try {
    return JSON.stringify(JSON.parse(content), null, 2);
  } catch {
    return content;
  }
}

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
      <InspectorTabButton tab="status" active={activeTab === "status"} icon={<StarbridgeStatusIcon size={14} strokeWidth={1.9} aria-hidden="true" />} label={t(locale, "inspector_status")} onClick={onChange} />
      <InspectorTabButton tab="review" active={activeTab === "review"} icon={<StarbridgeReviewIcon size={14} strokeWidth={1.9} aria-hidden="true" />} label={t(locale, "inspector_review")} onClick={onChange} />
      <InspectorTabButton tab="browser" active={activeTab === "browser"} icon={<StarbridgeBrowserIcon size={14} strokeWidth={1.9} aria-hidden="true" />} label={t(locale, "inspector_browser")} onClick={onChange} />
      <InspectorTabButton tab="files" active={activeTab === "files"} icon={<StarbridgeFilesIcon size={14} strokeWidth={1.9} aria-hidden="true" />} label={t(locale, "inspector_files")} onClick={onChange} />
    </nav>
  );
}

type ReviewDiffLineKind = "add" | "del" | "context" | "meta";

type ReviewDiffLine = {
  key: string;
  kind: ReviewDiffLineKind;
  oldLine?: number;
  newLine?: number;
  text: string;
};

type ReviewDiffHunk = {
  id: string;
  header: string;
  lines: ReviewDiffLine[];
};

function reviewPanelText(locale: Locale, key: "collapse" | "diffTruncated" | "remaining", count = 0) {
  if (locale === "zh-CN") {
    if (key === "collapse") return "收起";
    if (key === "diffTruncated") return "diff 已截断，仅显示前部内容。";
    return `还有 ${count} 条`;
  }
  if (key === "collapse") return "Collapse";
  if (key === "diffTruncated") return "Diff is truncated; showing the first section only.";
  return `${count} more`;
}

function reviewFileTimestamp(file: ProjectReviewFile): number {
  const value = file.updated_at;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const numeric = Number(value);
    if (Number.isFinite(numeric)) return numeric;
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return parsed / 1000;
  }
  return 0;
}

function sortedReviewFiles(files: ProjectReviewFile[]) {
  return files
    .map((file, index) => ({ file, index, timestamp: reviewFileTimestamp(file) }))
    .sort((a, b) => b.timestamp - a.timestamp || a.index - b.index)
    .map((item) => item.file);
}

function parseHunkStart(line: string) {
  const match = line.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$/);
  return {
    oldLine: match ? Number(match[1]) : 0,
    newLine: match ? Number(match[2]) : 0,
    title: match?.[3]?.trim() || "",
  };
}

function isDiffMetadata(line: string) {
  return (
    line.startsWith("diff --") ||
    line.startsWith("index ") ||
    line.startsWith("new file mode ") ||
    line.startsWith("deleted file mode ") ||
    line.startsWith("similarity index ") ||
    line.startsWith("rename from ") ||
    line.startsWith("rename to ") ||
    line.startsWith("--- ") ||
    line.startsWith("+++ ")
  );
}

function parseUnifiedDiff(diffText: string): ReviewDiffHunk[] {
  const hunks: ReviewDiffHunk[] = [];
  let current: ReviewDiffHunk | null = null;
  let oldLine = 0;
  let newLine = 0;

  const ensureCurrent = () => {
    if (!current) {
      current = { id: `hunk-${hunks.length}`, header: "Changes", lines: [] };
      hunks.push(current);
    }
    return current;
  };

  diffText.split(/\r?\n/).forEach((line, index) => {
    if (line.startsWith("@@")) {
      const parsed = parseHunkStart(line);
      oldLine = parsed.oldLine;
      newLine = parsed.newLine;
      current = {
        id: `hunk-${hunks.length}`,
        header: parsed.title ? `${line.slice(0, line.indexOf("@@", 2) + 2)} ${parsed.title}` : line,
        lines: [],
      };
      hunks.push(current);
      return;
    }
    if (!current && isDiffMetadata(line)) return;
    const target = ensureCurrent();
    if (line.startsWith("+") && !line.startsWith("+++")) {
      target.lines.push({ key: `${index}:add:${newLine}`, kind: "add", newLine, text: line.slice(1) || " " });
      newLine += 1;
      return;
    }
    if (line.startsWith("-") && !line.startsWith("---")) {
      target.lines.push({ key: `${index}:del:${oldLine}`, kind: "del", oldLine, text: line.slice(1) || " " });
      oldLine += 1;
      return;
    }
    if (line.startsWith(" ")) {
      target.lines.push({ key: `${index}:ctx:${oldLine}:${newLine}`, kind: "context", oldLine, newLine, text: line.slice(1) || " " });
      oldLine += 1;
      newLine += 1;
      return;
    }
    target.lines.push({ key: `${index}:meta`, kind: "meta", text: line || " " });
  });

  return hunks.filter((hunk) => hunk.lines.length);
}

function ReviewDiffCanvas({
  locale,
  diff,
  fallbackDetail,
}: {
  locale: Locale;
  diff?: ProjectReviewDiff;
  fallbackDetail?: string;
}) {
  const diffText = diff?.ok ? diff.diff : "";
  const hunks = useMemo(() => parseUnifiedDiff(diffText || ""), [diffText]);
  if (diff && !diff.ok) {
    return <div className="review-diff-canvas review-diff-message review-diff-error">{diff.error || t(locale, "review_diff_error")}</div>;
  }
  if (!diffText?.trim() && fallbackDetail) {
    return <pre className="review-diff-canvas review-diff-raw">{fallbackDetail}</pre>;
  }
  if (!diffText?.trim()) {
    return <div className="review-diff-canvas review-diff-message">{t(locale, "review_no_diff")}</div>;
  }
  if (!hunks.length) {
    return <pre className="review-diff-canvas review-diff-raw">{diffText}</pre>;
  }
  return (
    <div className="review-diff-canvas" aria-label={t(locale, "review_select_file")}>
      {diff?.truncated ? <div className="review-diff-truncated">{reviewPanelText(locale, "diffTruncated")}</div> : null}
      {hunks.map((hunk) => (
        <section className="review-diff-hunk" key={hunk.id}>
          <div className="review-diff-hunk-head">{hunk.header}</div>
          <div className="review-diff-lines">
            {hunk.lines.map((line) => (
              <div className={`review-diff-line review-diff-${line.kind}`} key={line.key}>
                <span className="review-diff-line-no">{line.oldLine ?? ""}</span>
                <span className="review-diff-line-no">{line.newLine ?? ""}</span>
                <code className="review-diff-code">{line.text}</code>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
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
  const [filesExpanded, setFilesExpanded] = useState(false);
  const sortedFiles = useMemo(() => sortedReviewFiles(files), [files]);
  const visibleFiles = filesExpanded ? sortedFiles.slice(0, 24) : sortedFiles.slice(0, 1);
  const latestPath = sortedFiles[0]?.path ?? "";
  const remainingCount = Math.max(0, sortedFiles.length - 1);
  const fallbackDetail = selectedPath ? fallback?.detailByPath[selectedPath] : "";
  const changedFileCount = Math.max(git?.changed_files ?? 0, sortedFiles.length);
  const gitLabel = git?.is_repo ? git.branch || "repo" : t(locale, "inspector_non_git");
  const selectedFile = sortedFiles.find((file) => file.path === selectedPath) ?? sortedFiles[0] ?? null;
  const selectedFileSecondary = selectedFile ? parentPathLabel(selectedFile.path) || selectedFile.path : gitLabel;

  useEffect(() => {
    if (!latestPath) return;
    if (!selectedPath || !sortedFiles.some((file) => file.path === selectedPath)) {
      onSelectPath(latestPath);
    }
  }, [latestPath, onSelectPath, selectedPath, sortedFiles]);

  return (
    <section className="inspector-tool-panel review-inspector-panel" data-testid="review-panel" aria-label={t(locale, "review_title")}>
      <div className="review-compact-summary">
        <span className="review-summary-chip">
          <span>{t(locale, "review_changed_files")}</span>
          <strong>{changedFileCount.toLocaleString()}</strong>
        </span>
        <span className="diff-progress-pill">
          <span className="diff-added">+{(git?.added ?? 0).toLocaleString()}</span>
          <span className="diff-deleted">-{(git?.deleted ?? 0).toLocaleString()}</span>
        </span>
        <span className="review-summary-branch" title={gitLabel}>{gitLabel}</span>
        {remainingCount ? (
          <button
            type="button"
            className="review-file-toggle"
            data-testid="review-file-toggle"
            aria-expanded={filesExpanded}
            onClick={() => setFilesExpanded((value) => !value)}
          >
            <span>{filesExpanded ? reviewPanelText(locale, "collapse") : reviewPanelText(locale, "remaining", remainingCount)}</span>
            {filesExpanded ? <ChevronUp size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />}
          </button>
        ) : null}
      </div>
      <div className="review-file-stack">
        {sortedFiles.length ? (
          <>
            <div className={`review-file-list ${filesExpanded ? "expanded" : ""}`} role="list" aria-label={t(locale, "review_changed_files")}>
              {visibleFiles.map((file) => (
                <button
                  type="button"
                  data-testid="review-file-row"
                  className={`review-file-row ${selectedPath === file.path ? "active" : ""}`}
                  onClick={() => onSelectPath(file.path)}
                  key={`${file.status}:${file.path}`}
                  title={file.path}
                >
                  <span className="review-file-copy">
                    <strong>{fileNameLabel(file.path)}</strong>
                    <small title={parentPathLabel(file.path) || file.path}>{parentPathLabel(file.path) || file.path}</small>
                  </span>
                  <small className="review-file-status" title={file.status}>{compactStatusCode(file.status)}</small>
                </button>
              ))}
            </div>
          </>
        ) : (
          <p className="muted compact-copy">{t(locale, "review_empty")}</p>
        )}
      </div>
      {selectedFile ? (
        <div className="review-current-file" title={selectedFile.path}>
          <span className="review-current-file-copy">
            <strong>{fileNameLabel(selectedFile.path)}</strong>
            <span>{selectedFileSecondary}</span>
          </span>
          <small className="review-file-status" title={selectedFile.status}>{compactStatusCode(selectedFile.status)}</small>
        </div>
      ) : null}
      <ReviewDiffCanvas locale={locale} diff={diff} fallbackDetail={fallbackDetail} />
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
  const diagnostics = facts.diagnosticRefs.filter((item) => item.kind !== "provider_handoff");
  const failedCommands = facts.commandRefs.filter((item) => String(item.status ?? "").toLowerCase() === "failed");
  const hasIssues = failedCommands.length > 0 || diagnostics.length > 0;
  const recoveryLabel = facts.recoveredCommandCount > 0
    ? locale === "zh-CN" ? `${facts.recoveredCommandCount} 条已恢复` : `${facts.recoveredCommandCount} recovered`
    : facts.failedCommandCount > 0
      ? locale === "zh-CN" ? `${facts.failedCommandCount} 条待处理` : `${facts.failedCommandCount} ${t(locale, "workflow_pending")}`
      : t(locale, "workflow_clear");
  return (
    <section className="pane-section inspector-section" data-testid="workflow-evidence-panel">
      <div className="section-header">
        <h2>{t(locale, "workflow_facts")}</h2>
        <span className={`mini-guard mini-guard-${hasIssues ? "warning" : "ok"}`}>{hasIssues ? recoveryLabel : t(locale, "workflow_clear")}</span>
      </div>
      {!hasIssues && !checkpoints.length ? <p className="muted compact-copy">{locale === "zh-CN" ? "工作流正常。" : "Workflow is clear."}</p> : null}
      {failedCommands.length ? (
        <div className="inspector-list" role="list" aria-label={t(locale, "workflow_commands")}>
          {failedCommands.slice(-3).map((item, index) => (
            <div className="inspector-list-row static-row" data-testid="workflow-command-row" key={`${item.command}:${index}`}>
              <span>{item.command}</span>
              <small>{item.status}</small>
            </div>
          ))}
        </div>
      ) : null}
      {checkpoints.length ? (
        <div className="inspector-list" role="list" aria-label={t(locale, "workflow_checkpoints")}>
          {checkpoints.slice(-2).map((item) => (
            <div className="inspector-list-row static-row" data-testid="workflow-checkpoint-row" key={item.save_id}>
              <span>{item.description}</span>
              <small>{item.save_id}</small>
            </div>
          ))}
        </div>
      ) : null}
      {diagnostics.length ? (
        <div className="inspector-list" role="list" aria-label={t(locale, "workflow_diagnostics")}>
          {diagnostics.slice(-3).map((item, index) => (
            <div className="inspector-list-row static-row" data-testid="workflow-diagnostic-row" key={`${item.kind}:${item.summary}:${index}`}>
              <span>{item.summary}</span>
              <small>{item.kind}</small>
            </div>
          ))}
        </div>
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
  const defaultUrl = useMemo(() => browser?.url || "about:blank", [browser?.url]);
  const [address, setAddress] = useState(defaultUrl === "about:blank" ? "" : defaultUrl);
  const [frameUrl, setFrameUrl] = useState(defaultUrl);
  const [sessions, setSessions] = useState<BrowserWorkbenchSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [isWorkbenchBusy, setIsWorkbenchBusy] = useState(false);
  const [workbenchError, setWorkbenchError] = useState("");
  const [computerUseReport, setComputerUseReport] = useState<ComputerUseBrowserScenarioReport | null>(null);
  const [webFrameReloadKey, setWebFrameReloadKey] = useState(0);
  const [browserStageSize, setBrowserStageSize] = useState({ width: 0, height: 0 });
  const browserFrameRef = useRef<HTMLIFrameElement | null>(null);
  const browserStageRef = useRef<HTMLDivElement | null>(null);
  const browserLayoutRequestRef = useRef("");
  const selectedSession = sessions.find((item) => item.id === selectedSessionId) ?? sessions[0] ?? null;
  const showDevPreview = frameUrl !== "about:blank" && !isSelfPreviewUrl(frameUrl);

  function replaceSession(nextSession: BrowserWorkbenchSession) {
    setSessions((current) => {
      const filtered = current.filter((item) => item.id !== nextSession.id);
      return [...filtered, nextSession].sort((left, right) => left.role.localeCompare(right.role));
    });
  }

  useEffect(() => {
    let cancelled = false;
    api
      .browserList()
      .then((items) => {
        if (cancelled) return;
        setWorkbenchError("");
        setSessions(items);
        setSelectedSessionId((current) => (current && items.some((item) => item.id === current) ? current : items[0]?.id ?? ""));
      })
      .catch((error) => {
        if (!cancelled) setWorkbenchError(error instanceof Error ? error.message : String(error));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const node = browserStageRef.current;
    if (!node) return undefined;
    const measure = () => {
      const rect = node.getBoundingClientRect();
      setBrowserStageSize((current) => {
        const width = Math.round(rect.width);
        const height = Math.round(rect.height);
        return current.width === width && current.height === height ? current : { width, height };
      });
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [selectedSessionId, sessions.length]);

  useEffect(() => {
    if (!sessions.length) return undefined;
    const timer = window.setInterval(() => {
      void refreshWorkbench().catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [sessions.length]);

  async function refreshWorkbench() {
    const items = await api.browserList();
    setWorkbenchError("");
    setSessions(items);
    setSelectedSessionId((current) => (current && items.some((item) => item.id === current) ? current : items[0]?.id ?? ""));
    return items;
  }

  async function runWorkbench(action: () => Promise<void>) {
    setIsWorkbenchBusy(true);
    setWorkbenchError("");
    try {
      await action();
    } catch (error) {
      setWorkbenchError(error instanceof Error ? error.message : String(error));
    } finally {
      setIsWorkbenchBusy(false);
    }
  }

  function currentStageSize() {
    const rect = browserStageRef.current?.getBoundingClientRect();
    return {
      width: browserStageSize.width || Math.round(rect?.width || 0),
      height: browserStageSize.height || Math.round(rect?.height || 0),
    };
  }

  function preferredRemoteLayoutMode() {
    const size = currentStageSize();
    return desiredBrowserLayoutMode({ isRemote: true, width: size.width, height: size.height });
  }

  function browserLayoutReason(mode: "desktop" | "mobile") {
    return mode === "mobile"
      ? "right inspector is tall/narrow; request responsive mobile viewport and mobile user agent"
      : "right inspector is wide enough for desktop viewport";
  }

  function handleBrowse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = normalizeBrowserUrl(address);
    setAddress(normalized);
    setFrameUrl(normalized);
    if (selectedSessionId || sessions[0]?.id) {
      navigateSelectedBrowser(normalized);
      return;
    }
    openManagedBrowser();
  }

  function openManagedBrowser() {
    void runWorkbench(async () => {
      const url = normalizeManagedBrowserUrl(address);
      const layoutMode = preferredRemoteLayoutMode();
      const session = await api.browserCreate({
        id: `manual-${Date.now()}`,
        role: roleFromUrl(url),
        url,
        layout_mode: layoutMode,
        layout_reason: browserLayoutReason(layoutMode),
      });
      replaceSession(session);
      setSelectedSessionId(session.id);
      setAddress(session.url || url);
      setFrameUrl(session.url || url);
      await refreshWorkbench();
    });
  }

  function navigateSelectedBrowser(nextAddress?: string) {
    void runWorkbench(async () => {
      const id = selectedSessionId || sessions[0]?.id;
      if (!id) throw new Error(t(locale, "browser_workbench_select_first"));
      const url = normalizeManagedBrowserUrl(nextAddress || address);
      const layoutMode = preferredRemoteLayoutMode();
      const session = await api.browserNavigate({
        id,
        url,
        layout_mode: layoutMode,
        layout_reason: browserLayoutReason(layoutMode),
      });
      replaceSession(session);
      setSelectedSessionId(session.id);
      setAddress(session.url || url);
      setFrameUrl(session.url || url);
      await refreshWorkbench();
    });
  }

  function openNewsYoutubeScenario() {
    void runWorkbench(async () => {
      const layoutMode = preferredRemoteLayoutMode();
      const news = await api.browserCreate({
        id: "news",
        role: "News",
        url: "https://news.google.com/search?q=%E5%AE%9E%E6%97%B6%E6%96%B0%E9%97%BB&hl=zh-CN&gl=US&ceid=US:zh-Hans",
        layout_mode: layoutMode,
        layout_reason: browserLayoutReason(layoutMode),
      });
      const youtube = await api.browserCreate({
        id: "youtube",
        role: "YouTube",
        url: "https://www.youtube.com/",
        layout_mode: layoutMode,
        layout_reason: browserLayoutReason(layoutMode),
      });
      await api.browserTileTwoUp([news.id, youtube.id]);
      const report = await api.runtimeComputerUseBrowserScenario({
        run_model: true,
        include_yunwu: true,
        allow_fallback_sites: true,
        max_wait_sec: 8,
      });
      setComputerUseReport(report);
      await refreshWorkbench();
    });
  }

  function closeBrowser(id: string) {
    void runWorkbench(async () => {
      const items = await api.browserClose(id);
      setSessions(items);
      setSelectedSessionId((current) => (current === id ? items[0]?.id ?? "" : current));
    });
  }

  function selectBrowserSession(session: BrowserWorkbenchSession) {
    setSelectedSessionId(session.id);
    if (session.url) {
      setAddress(session.url);
      setFrameUrl(session.url);
    }
  }

  function focusSelectedBrowser() {
    if (!selectedSession) return;
    void runWorkbench(async () => {
      const session = await api.browserFocus(selectedSession.id);
      replaceSession(session);
      setSelectedSessionId(session.id);
      await refreshWorkbench();
    });
  }

  function interactWithBrowserSurface(payload: Parameters<typeof api.browserAction>[0]) {
    void runWorkbench(async () => {
      const session = await api.browserAction(payload);
      replaceSession(session);
      setSelectedSessionId(session.id);
      if (session.url) {
        setAddress(session.url);
        setFrameUrl(session.url);
      }
      await refreshWorkbench();
    });
  }

  function interactWithRemoteSnapshot(
    event: MouseEvent<HTMLDivElement>,
    action: "click" | "double_click",
  ) {
    if (!selectedSession || isWorkbenchBusy) return;
    const imageRect = event.currentTarget.querySelector("img")?.getBoundingClientRect();
    const fallbackRect = event.currentTarget.getBoundingClientRect();
    const rect = imageRect && imageRect.width > 0 && imageRect.height > 0 ? imageRect : fallbackRect;
    const viewportWidth = selectedSession.viewport_width || 1365;
    const viewportHeight = selectedSession.viewport_height || 900;
    const x = ((event.clientX - rect.left) / Math.max(rect.width, 1)) * viewportWidth;
    const y = ((event.clientY - rect.top) / Math.max(rect.height, 1)) * viewportHeight;
    interactWithBrowserSurface({ id: selectedSession.id, action, x, y });
  }

  function scrollRemoteSnapshot(event: WheelEvent<HTMLDivElement>) {
    if (!selectedSession || isWorkbenchBusy) return;
    event.preventDefault();
    interactWithBrowserSurface({
      id: selectedSession.id,
      action: "scroll",
      delta_x: Math.round(event.deltaX),
      delta_y: Math.round(event.deltaY),
    });
  }

  const selectedManagedSession = Boolean(selectedSession && selectedSession.preview_mode !== "web_fallback");

  function navigateEmbeddedFrame(direction: "back" | "forward") {
    if (selectedManagedSession && selectedSession) {
      interactWithBrowserSurface({ id: selectedSession.id, action: direction });
      return;
    }
    const frameWindow = browserFrameRef.current?.contentWindow;
    if (!frameWindow) return;
    try {
      if (direction === "back") {
        frameWindow.history.back();
      } else {
        frameWindow.history.forward();
      }
    } catch {
      setWebFrameReloadKey((current) => current + 1);
    }
  }

  function reloadEmbeddedFrame() {
    if (selectedManagedSession && selectedSession) {
      interactWithBrowserSurface({ id: selectedSession.id, action: "reload" });
      return;
    }
    const frameWindow = browserFrameRef.current?.contentWindow;
    if (!frameWindow) return;
    try {
      frameWindow.location.reload();
    } catch {
      setWebFrameReloadKey((current) => current + 1);
    }
  }

  const browserStatus = selectedSession
    ? browserStatusTextBrand(locale, selectedSession.status)
    : browser?.status
      ? statusLabel(browser.status)
      : t(locale, "inspector_not_run");
  const browserConsoleCount = browser?.console_errors?.length ?? 0;
  const browserRequestCount = browser?.request_failures?.length ?? 0;
  const screenshotPreviewUrl = browser?.screenshot_path && !selectedSession ? projectFileMediaHref(browser.screenshot_path) : "";
  const selectedRole = selectedSession ? browserRoleTextBrand(locale, selectedSession.role) : browser?.label || t(locale, "browser_preview");
  const selectedSessionIsNative = selectedSession?.preview_mode === "native";
  const selectedSessionIsRemote = selectedSession?.preview_mode === "remote";
  const selectedSupervisorScreenshotUrl = selectedSession?.screenshot_path ? projectFileMediaHref(selectedSession.screenshot_path) : "";
  const selectedRemoteFrameUrl = selectedSessionIsRemote ? api.browserWorkbenchFrameHref(selectedSession.id, selectedSession.updated_at) : "";
  const selectedRemoteLiveFrameUrl = selectedSessionIsRemote ? browserLiveFrameUrl(selectedSession) : "";
  const currentStageRect = browserStageRef.current?.getBoundingClientRect();
  const effectiveBrowserStageWidth = browserStageSize.width || Math.round(currentStageRect?.width || 0);
  const effectiveBrowserStageHeight = browserStageSize.height || Math.round(currentStageRect?.height || 0);
  const browserStageAspect = browserStageAspectRatio(effectiveBrowserStageWidth, effectiveBrowserStageHeight);
  const desiredRemoteLayoutMode = desiredBrowserLayoutMode({
    isRemote: selectedSessionIsRemote,
    width: effectiveBrowserStageWidth,
    height: effectiveBrowserStageHeight,
  });
  const remotePeerSession = selectedSessionIsRemote
    ? sessions.find((session) => session.preview_mode === "remote" && session.id !== selectedSession?.id) ?? null
    : null;
  const shouldStackRemoteSessions = !selectedRemoteLiveFrameUrl && shouldUseBrowserTwoPageStack({
    isRemote: selectedSessionIsRemote,
    desiredMode: desiredRemoteLayoutMode,
    aspect: browserStageAspect,
    mobileOptimized: selectedSession?.mobile_optimized,
    responsiveFitScore: selectedSession?.responsive_fit_score,
    hasPeer: Boolean(remotePeerSession),
  });
  const embeddedPageUrl = selectedSessionIsNative || selectedSessionIsRemote ? "" : selectedSession?.url || (showDevPreview ? frameUrl : "");
  const canNavigateBrowser = Boolean(selectedSession || embeddedPageUrl);
  const hasBrowserWarnings = browserRequestCount > 0 || browserConsoleCount > 0 || Boolean(browser?.status && browser.status !== "pass") || Boolean(selectedSession?.error);
  const browserDetailCount = [browserConsoleCount > 0, browserRequestCount > 0, Boolean(computerUseReport), Boolean(workbenchError)].filter(Boolean).length;
  const browserDetailSummary = browserDetailCount > 0
    ? locale === "zh-CN" ? `详情与操作 (${browserDetailCount})` : `Details & actions (${browserDetailCount})`
    : locale === "zh-CN" ? "详情与操作" : "Details & actions";
  const compactArtifact = computerUseReport?.artifact_path ? compactPathLabel(computerUseReport.artifact_path) || fileNameLabel(computerUseReport.artifact_path) : "";
  const screenshotState = browser?.screenshot_path ? (locale === "zh-CN" ? "已截图" : "captured") : t(locale, "browser_evidence_not_captured");
  const renderSummary = browserRenderSummaryBrand(locale, selectedSession, {
    desiredMode: desiredRemoteLayoutMode,
    stackMode: shouldStackRemoteSessions,
  });
  const browserCanvasTitle = selectedSession
    ? String(selectedSession.page_title || "").trim() || browserUrlChromeLabel(selectedSession.url) || selectedRole
    : browser?.label || t(locale, "browser_title");
  const browserCanvasMode = renderSummary?.mode || (selectedSessionIsNative ? (locale === "zh-CN" ? "前台窗口" : "Foreground window") : browserStatus);
  const browserCanvasDetail = renderSummary?.detail || (selectedSession?.loading ? (locale === "zh-CN" ? "加载中" : "Loading") : "");
  const browserCanvasTone = workbenchError ? "warning" : hasBrowserWarnings ? "warning" : renderSummary?.tone || "desktop";
  const browserDetailSummarySafe = browserDetailCount > 0
    ? locale === "zh-CN" ? `详情与操作 (${browserDetailCount})` : `Details & actions (${browserDetailCount})`
    : locale === "zh-CN" ? "详情与操作" : "Details & actions";
  const screenshotStateSafe = browser?.screenshot_path ? (locale === "zh-CN" ? "已截图" : "captured") : t(locale, "browser_evidence_not_captured");
  const browserCanvasSubtitleSafe = selectedSession
    ? [
        browserRoleTextBrand(locale, selectedSession.role),
        browserUrlChromeLabel(selectedSession.url),
        selectedSessionIsNative
          ? (locale === "zh-CN" ? "前台 WebView2" : "Foreground WebView2")
          : selectedRemoteLiveFrameUrl
            ? (locale === "zh-CN" ? "实时页面" : "Live page")
            : selectedRemoteFrameUrl
              ? (locale === "zh-CN" ? "托管快照" : "Managed snapshot")
              : embeddedPageUrl
                ? (locale === "zh-CN" ? "内嵌预览" : "Inline preview")
                : "",
      ].filter(Boolean).join(" · ")
    : locale === "zh-CN"
      ? "还没有打开页面。输入地址后，右栏会在这里显示实时页面、移动端渲染或托管快照。"
      : "No page is open yet. After you enter a URL, the right pane will show a live page, a mobile render, or a managed snapshot here.";

  useEffect(() => {
    if (!selectedSessionIsRemote || !selectedSession || isWorkbenchBusy || effectiveBrowserStageWidth <= 0) return;
    if (selectedSession.layout_mode === desiredRemoteLayoutMode) return;
    const requestKey = `${selectedSession.id}:${desiredRemoteLayoutMode}`;
    if (browserLayoutRequestRef.current === requestKey) return;
    browserLayoutRequestRef.current = requestKey;
    void runWorkbench(async () => {
      const session = await api.browserLayout({
        id: selectedSession.id,
        layout_mode: desiredRemoteLayoutMode,
        layout_reason:
          desiredRemoteLayoutMode === "mobile"
            ? "right inspector is tall and narrow; prefer mobile responsive rendering"
            : "right inspector has enough width for desktop rendering",
      });
      replaceSession(session);
      if (session.url) {
        setAddress(session.url);
        setFrameUrl(session.url);
      }
    });
  }, [desiredRemoteLayoutMode, effectiveBrowserStageHeight, effectiveBrowserStageWidth, isWorkbenchBusy, selectedSession?.id, selectedSession?.layout_mode, selectedSessionIsRemote]);

  useEffect(() => {
    if (!shouldStackRemoteSessions || !remotePeerSession || isWorkbenchBusy) return;
    if (remotePeerSession.layout_mode === desiredRemoteLayoutMode) return;
    const requestKey = `${remotePeerSession.id}:${desiredRemoteLayoutMode}`;
    if (browserLayoutRequestRef.current === requestKey) return;
    browserLayoutRequestRef.current = requestKey;
    void runWorkbench(async () => {
      const session = await api.browserLayout({
        id: remotePeerSession.id,
        layout_mode: desiredRemoteLayoutMode,
        layout_reason: "secondary page in tall split browser surface",
      });
      replaceSession(session);
    });
  }, [desiredRemoteLayoutMode, isWorkbenchBusy, remotePeerSession?.id, remotePeerSession?.layout_mode, shouldStackRemoteSessions]);

  function remoteSnapshotClass(session: BrowserWorkbenchSession, extra = "") {
    return ["browser-remote-snapshot-surface", session.layout_mode === "mobile" ? "mobile" : "", extra].filter(Boolean).join(" ");
  }

  return (
    <section className="inspector-tool-panel browser-inspector-panel" data-testid="browser-panel" aria-label={t(locale, "browser_title")}>
      <div className="browser-chrome-shell">
        {sessions.length ? (
          <div className="browser-workbench-strip" data-testid="browser-workbench">
            <div className="browser-workbench-tabs" role="tablist" aria-label={t(locale, "browser_workbench_title")}>
              {sessions.map((session) => (
                <div className={`browser-workbench-tab ${selectedSessionId === session.id ? "active" : ""}`} data-testid="browser-workbench-row" key={session.id}>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={selectedSessionId === session.id}
                    className="browser-workbench-main"
                    onClick={() => selectBrowserSession(session)}
                    title={`${browserTabLineBrand(locale, session)}${session.mobile_strategy ? ` | ${browserMobileStrategyTextBrand(locale, session.mobile_strategy)}` : ""}`}
                  >
                    <span className="browser-workbench-line" title={session.url}>
                      {browserTabLineBrand(locale, session)}
                    </span>
                  </button>
                  <button type="button" className="ghost-button inspector-inline-action icon-button" disabled={isWorkbenchBusy} onClick={() => closeBrowser(session.id)} title={t(locale, "browser_workbench_close")} aria-label={t(locale, "browser_workbench_close")}>
                    <X size={13} aria-hidden="true" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <form className="browser-compact-toolbar" onSubmit={handleBrowse}>
          <span
            className={`browser-status-chip ${selectedSession?.status === "open" || selectedSession?.status === "focused" || browser?.status === "pass" ? "status-ok" : hasBrowserWarnings ? "status-warning" : ""}`}
            title={`${t(locale, "browser_recent_smoke")}: ${browserStatus}`}
          >
            <strong>{browserStatus}</strong>
          </span>
          <input
            className="inspector-search browser-address-input"
            data-testid="browser-address-input"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            placeholder={t(locale, "browser_url_placeholder")}
            aria-label={t(locale, "browser_url_placeholder")}
          />
          {renderSummary && renderSummary.tone !== "desktop" ? (
            <span
              className={`browser-toolbar-meta tone-${renderSummary.tone}`}
              data-testid="browser-toolbar-meta"
              title={renderSummary.title}
            >
              <strong>{renderSummary.mode}</strong>
              <span>{renderSummary.detail}</span>
            </span>
          ) : null}
          <button type="submit" className="ghost-button inspector-inline-action" data-testid="browser-go-button">
            {t(locale, "browser_go")}
          </button>
          <div className="browser-toolbar-nav" data-testid="browser-toolbar-nav">
            <button type="button" className="ghost-button inspector-inline-action icon-button" disabled={!canNavigateBrowser || isWorkbenchBusy} onClick={() => navigateEmbeddedFrame("back")} title={locale === "zh-CN" ? "后退" : "Back"} aria-label={locale === "zh-CN" ? "后退" : "Back"}>
              <ArrowLeft size={13} aria-hidden="true" />
            </button>
            <button type="button" className="ghost-button inspector-inline-action icon-button" disabled={!canNavigateBrowser || isWorkbenchBusy} onClick={() => navigateEmbeddedFrame("forward")} title={locale === "zh-CN" ? "前进" : "Forward"} aria-label={locale === "zh-CN" ? "前进" : "Forward"}>
              <ArrowRight size={13} aria-hidden="true" />
            </button>
            <button type="button" className="ghost-button inspector-inline-action icon-button" data-testid="browser-reload-button" disabled={!canNavigateBrowser || isWorkbenchBusy} onClick={reloadEmbeddedFrame} title={locale === "zh-CN" ? "刷新页面" : "Reload page"} aria-label={locale === "zh-CN" ? "刷新页面" : "Reload page"}>
              <RefreshCw size={13} aria-hidden="true" />
            </button>
            <button type="button" className="ghost-button inspector-inline-action icon-button" data-testid="browser-open-button" onClick={openManagedBrowser} disabled={isWorkbenchBusy} title={t(locale, "browser_workbench_open")} aria-label={t(locale, "browser_workbench_open")}>
              <ExternalLink size={13} aria-hidden="true" />
            </button>
          </div>
        </form>
      </div>

      <div
        className="browser-webview"
        data-testid="browser-surface"
        data-layout-mode={selectedSessionIsRemote ? desiredRemoteLayoutMode : "embedded"}
        data-stack-mode={shouldStackRemoteSessions ? "two-page" : "single-page"}
        data-mobile-strategy={selectedSession?.mobile_strategy || selectedSession?.layout_mode || "desktop"}
      >
        <div className="browser-webview-stage" ref={browserStageRef}>
          <div className={`browser-canvas-bar tone-${browserCanvasTone}`} data-testid="browser-canvas-bar">
            <div className="browser-canvas-title">
              <div className="browser-canvas-title-head">
                <StarbridgeBrowserIcon size={15} strokeWidth={1.9} aria-hidden="true" />
                <strong title={browserCanvasTitle}>{browserCanvasTitle}</strong>
              </div>
              <span title={browserCanvasSubtitleSafe}>{browserCanvasSubtitleSafe}</span>
            </div>
            <div className="browser-canvas-actions">
              <span className={`browser-surface-chip tone-${browserCanvasTone}`} title={browserRenderSummaryBrand(locale, selectedSession, { desiredMode: desiredRemoteLayoutMode, stackMode: shouldStackRemoteSessions })?.title || browserStatus}>
                {browserCanvasMode}
              </span>
              {browserCanvasDetail ? (
                <span className="browser-surface-chip subtle" title={browserCanvasDetail}>
                  {browserCanvasDetail}
                </span>
              ) : null}
            </div>
          </div>
          <div className="browser-canvas-stage" data-testid="browser-canvas-stage">
          {selectedSessionIsNative ? (
            <div className="browser-native-surface" data-testid="browser-native-surface">
              <div className="browser-native-copy">
                <strong>{locale === "zh-CN" ? "原生浏览器窗口已打开" : "Native browser window is open"}</strong>
                <small>
                  {locale === "zh-CN" ? "监督状态" : "Supervision"}: {selectedSession.supervision_status || "-"}
                </small>
                <span title={selectedSession.url}>
                  {locale === "zh-CN"
                    ? "Google、YouTube 等禁止 iframe 的网站会在 WebView2 前台窗口中运行；后台监督会保留截图和状态。"
                    : "Sites that block iframe embedding run in a foreground WebView2 window; background supervision keeps snapshots and state."}
                </span>
              </div>
              <button type="button" className="ghost-button inspector-inline-action" onClick={focusSelectedBrowser} disabled={isWorkbenchBusy}>
                <ExternalLink size={13} aria-hidden="true" />
                <span>{locale === "zh-CN" ? "显示浏览器窗口" : "Show browser window"}</span>
              </button>
              {selectedSupervisorScreenshotUrl ? (
                <img className="browser-native-snapshot" src={selectedSupervisorScreenshotUrl} alt={locale === "zh-CN" ? "后台监督快照" : "Background supervision snapshot"} />
              ) : (
                <div className="browser-native-placeholder">
                  {locale === "zh-CN" ? "后台监督启动后会在这里显示快照。" : "A supervision snapshot will appear here after the background browser starts."}
                </div>
              )}
            </div>
          ) : selectedRemoteLiveFrameUrl ? (
            <div
              className="browser-frame-shell browser-live-frame-shell browser-remote-live-shell"
              data-testid="browser-remote-surface"
            >
              <iframe
                key={`${selectedSession?.id || "remote-live"}:${selectedRemoteLiveFrameUrl}:${webFrameReloadKey}`}
                ref={browserFrameRef}
                data-testid="browser-live-frame"
                src={selectedRemoteLiveFrameUrl}
                title={selectedSession?.page_title || selectedRole}
                referrerPolicy="no-referrer"
              />
            </div>
          ) : selectedRemoteFrameUrl ? (
            shouldStackRemoteSessions && remotePeerSession ? (
              <div className="browser-remote-stack" data-testid="browser-remote-stack">
                {[selectedSession, remotePeerSession].map((session, index) => (
                  <div
                    className={remoteSnapshotClass(session, index === 0 ? "primary" : "secondary")}
                    data-testid={index === 0 ? "browser-remote-snapshot-surface" : "browser-remote-stack-peer"}
                    key={session.id}
                    onClick={(event) => {
                      if (index === 0) {
                        interactWithRemoteSnapshot(event, "click");
                      } else {
                        selectBrowserSession(session);
                      }
                    }}
                    onDoubleClick={(event) => {
                      if (index === 0) interactWithRemoteSnapshot(event, "double_click");
                    }}
                    onWheel={index === 0 ? scrollRemoteSnapshot : undefined}
                    title={index === 0 ? browserMobileSurfaceTitleBrand(locale, session, true) : `${browserRoleTextBrand(locale, session.role)} ${browserUrlChromeLabel(session.url)}`}
                  >
                    <img
                      className="browser-remote-snapshot"
                      src={api.browserWorkbenchFrameHref(session.id, session.updated_at)}
                      alt={session.page_title || session.role || "Browser"}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div
                className={remoteSnapshotClass(selectedSession)}
                data-testid="browser-remote-snapshot-surface"
                onClick={(event) => interactWithRemoteSnapshot(event, "click")}
                onDoubleClick={(event) => interactWithRemoteSnapshot(event, "double_click")}
                onWheel={scrollRemoteSnapshot}
                title={browserMobileSurfaceTitleBrand(locale, selectedSession, false)}
              >
                <img
                  className="browser-remote-snapshot"
                  src={selectedRemoteFrameUrl}
                  alt={selectedSession.page_title || selectedSession.role || "Browser"}
                />
              </div>
            )
          ) : embeddedPageUrl ? (
            <div
              className="browser-frame-shell browser-live-frame-shell"
              data-testid="browser-remote-surface"
            >
              <iframe
                key={`${selectedSession?.id || "preview"}:${embeddedPageUrl}:${webFrameReloadKey}`}
                ref={browserFrameRef}
                data-testid="browser-live-frame"
                src={embeddedPageUrl}
                title={selectedRole}
                referrerPolicy="no-referrer"
              />
            </div>
          ) : screenshotPreviewUrl ? (
            <div className="browser-screenshot-preview">
              <img src={screenshotPreviewUrl} alt={browser?.label || t(locale, "browser_screenshot")} />
            </div>
          ) : !showDevPreview ? (
            <div className="browser-canvas-empty">
              <div className="browser-canvas-empty-icon" aria-hidden="true">
                <StarbridgeBrowserIcon size={20} strokeWidth={1.9} />
              </div>
              <strong>{t(locale, "browser_workbench_surface_window")}</strong>
              <span>{selectedSession ? (locale === "zh-CN" ? "实时页面在托管浏览器中。" : "The live page is in the managed browser.") : t(locale, "browser_preview_empty")}</span>
            </div>
          ) : (
            <div className="browser-frame-shell">
              <iframe
                data-testid="browser-preview-frame"
                src={frameUrl}
                title={t(locale, "browser_preview")}
                referrerPolicy="no-referrer"
                sandbox="allow-downloads allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts"
              />
            </div>
          )}
          </div>
        </div>
      </div>

      {workbenchError ? (
        <div className="browser-workbench-error" role="alert" data-testid="browser-workbench-error">
          <strong>{t(locale, "browser_workbench_error_title")}</strong>
          <span>{workbenchError}</span>
        </div>
      ) : null}
      <details className="browser-details-panel">
        <summary>{browserDetailSummarySafe}</summary>
        <div className="browser-diagnostics-strip" aria-label={t(locale, "browser_evidence_label")}>
          <span title={browser?.label || undefined}>{t(locale, "browser_label")}: <strong>{browser?.label || "-"}</strong></span>
          {renderSummary ? (
            <span title={renderSummary.title}>{locale === "zh-CN" ? "渲染" : "Render"}: <strong>{renderSummary.mode}</strong></span>
          ) : null}
          <span>{t(locale, "browser_console")}: <strong>{browserConsoleCount}</strong></span>
          <span className={browserRequestCount > 0 ? "browser-diagnostic-warning" : ""}>{t(locale, "browser_request_failures")}: <strong>{browserRequestCount}</strong></span>
          <span title={browser?.screenshot_path || undefined}>{t(locale, "browser_screenshot")}: <strong>{screenshotStateSafe}</strong></span>
        </div>
        {computerUseReport ? (
          <div className="browser-workbench-report" data-testid="browser-cua-report">
            <span>{reportStatusLabel(locale, computerUseReport.status)}</span>
            <em>{reportModelStatus(locale, computerUseReport)}</em>
            <small title={computerUseReport.artifact_path}>{compactArtifact || computerUseReport.artifact_path}</small>
          </div>
        ) : null}
        {browser?.request_failures?.length ? (
          <pre className="tool-preview browser-request-preview">
            {browser.request_failures
              .slice(0, 4)
              .map((item) => [item.method, item.resource_type, item.error_text, browserUrlChromeLabel(item.url)].filter(Boolean).join(" | "))
              .join("\n")}
          </pre>
        ) : null}
        <div className="browser-workbench-actions">
            <button type="button" className="ghost-button inspector-inline-action" data-testid="browser-open-scenario-button" disabled={isWorkbenchBusy} onClick={openNewsYoutubeScenario}>
              <Grid2X2 size={13} aria-hidden="true" />
              <span>{t(locale, "browser_workbench_open_scenario")}</span>
            </button>
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
      </details>
    </section>
  );
}

function FilePreviewCanvas({
  locale,
  project,
  preview,
  mediaUrl,
  previewError,
  mediaError,
  selectedPath,
  selectedText,
  fallbackDetail,
  loading,
  canOpenRaw,
}: {
  locale: Locale;
  project: ProjectFile;
  preview?: ProjectFilePreview;
  mediaUrl?: string;
  previewError?: string;
  mediaError?: string;
  selectedPath?: string;
  selectedText: string;
  fallbackDetail?: string;
  loading?: boolean;
  canOpenRaw: boolean;
}) {
  const title = preview?.path || selectedPath || filePanelText(locale, "workspace");
  const titleName = fileNameLabel(title) || title;
  const titleParent = parentPathLabel(title) || (!preview && !selectedPath ? project.workspace_root : "");
  const showCanvasBar = Boolean(preview || selectedPath || fallbackDetail);
  const meta = preview
    ? [fileKindLabel(locale, preview.kind), formatBytes(preview.size), preview.mime_type || ""].filter(Boolean).join(" · ")
    : fallbackDetail
      ? filePanelText(locale, "eventSummary")
      : project.workspace_root;
  const mediaPreviewKinds = new Set(["image", "pdf", "audio", "video"]);
  const showPreviewError = Boolean(previewError);
  const showMediaError = !showPreviewError && Boolean(mediaError && preview && mediaPreviewKinds.has(preview.kind) && !preview.data_url && !mediaUrl);
  const surfaceError = previewError || mediaError || "";
  const safeMeta = preview
    ? [fileKindLabel(locale, preview.kind), formatBytes(preview.size), preview.mime_type || ""].filter(Boolean).join(" · ")
    : meta;

  return (
    <div className="file-canvas" data-testid="file-canvas">
      {showCanvasBar ? (
        <div className="file-canvas-bar">
          <div className="file-canvas-title">
            <strong title={title}>{titleName}</strong>
            <span title={titleParent || safeMeta}>{titleParent || safeMeta}</span>
          </div>
          <div className="file-canvas-actions">
            {loading ? <span className="file-loading-pill">{filePanelText(locale, "loading")}</span> : null}
            {preview ? <span className="file-meta-pill" title={safeMeta}>{safeMeta}</span> : null}
            {canOpenRaw && mediaUrl ? (
              <a className="ghost-button inspector-inline-action icon-button" href={mediaUrl} target="_blank" rel="noreferrer" title={filePanelText(locale, "openRaw")} aria-label={filePanelText(locale, "openRaw")}>
                <ExternalLink size={13} aria-hidden="true" />
              </a>
            ) : null}
          </div>
        </div>
      ) : null}
      <div className="file-canvas-stage" data-testid="file-canvas-stage">
        {showPreviewError || showMediaError ? (
          <div className="file-canvas-empty file-canvas-error" role="alert">
            <strong>{selectedPath ? fileNameLabel(selectedPath) : filePanelText(locale, "preview")}</strong>
            <span>{surfaceError}</span>
          </div>
        ) : null}
        {preview?.kind === "image" && (preview.data_url || mediaUrl) ? (
          <div className="file-canvas-image">
            <img src={preview.data_url ?? mediaUrl} alt={preview.name} />
          </div>
        ) : null}
        {preview?.kind === "markdown" ? <div className="markdown-preview file-canvas-document">{renderMarkdownPreview(preview.content ?? "")}</div> : null}
        {preview?.kind === "json" || preview?.kind === "text" ? <pre className="tool-preview file-text-preview file-canvas-code">{selectedText}</pre> : null}
        {preview?.kind === "pdf" && mediaUrl ? <iframe className="file-preview-frame file-canvas-frame" title={preview.name} src={`${mediaUrl}#zoom=page-fit`} /> : null}
        {preview?.kind === "audio" && mediaUrl ? <audio className="file-media-control file-canvas-media" controls src={mediaUrl} /> : null}
        {preview?.kind === "video" && mediaUrl ? <video className="file-media-control file-canvas-media" controls src={mediaUrl} /> : null}
        {!showPreviewError && !showMediaError && preview && !["text", "markdown", "json", "image", "pdf", "audio", "video"].includes(preview.kind) ? (
          <div className="file-canvas-empty">
            <strong>{fileKindLabel(locale, preview.kind)}</strong>
            <span>{preview.message ?? t(locale, "files_unsupported")}</span>
          </div>
        ) : null}
        {!showPreviewError && !showMediaError && !preview && fallbackDetail ? <pre className="tool-preview file-text-preview file-canvas-code">{fallbackDetail}</pre> : null}
        {!showPreviewError && !showMediaError && !preview && !fallbackDetail ? (
          <div className="file-canvas-empty">
            <strong>{selectedPath ? fileNameLabel(selectedPath) : filePanelText(locale, "workspace")}</strong>
            <span>{selectedPath ? (loading ? filePanelText(locale, "loading") : locale === "zh-CN" ? "暂无预览。" : "No preview yet.") : project.workspace_root}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function FilesInspectorPanel({
  locale,
  project,
  tree,
  preview,
  mediaUrl,
  previewLoading,
  previewError,
  mediaError,
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
  mediaUrl?: string;
  previewLoading?: boolean;
  previewError?: string;
  mediaError?: string;
  fallback?: CodingEventInspectorSummary;
  query: string;
  selectedPath?: string;
  onQueryChange: (value: string) => void;
  onSelectPath: (path: string) => void;
}) {
  const items = (tree?.items?.length ? tree.items : fallback?.recentFiles) ?? [];
  const fallbackDetail = selectedPath ? fallback?.detailByPath[selectedPath] : "";
  const selectedText = prettyText(preview?.kind, preview?.content);
  const canOpenRaw = Boolean(mediaUrl && preview && preview.kind !== "too_large");
  const [filesExpanded, setFilesExpanded] = useState(false);
  const visibleItems = filesExpanded ? items.slice(0, 80) : items.slice(0, 1);
  const remainingCount = Math.max(0, items.length - 1);
  const workspaceLabel = tree?.workspace_root || project.workspace_root;
  const firstItemPath = items[0]?.path ?? "";

  useEffect(() => {
    if (!firstItemPath) return;
    if (!selectedPath || !items.some((item) => item.path === selectedPath)) {
      onSelectPath(firstItemPath);
    }
  }, [firstItemPath, items, onSelectPath, selectedPath]);

  return (
    <section className="inspector-tool-panel files-inspector-panel" data-testid="files-panel" aria-label={t(locale, "files_title")}>
      <div className="files-search-row">
        <input className="inspector-search files-search-input" value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder={t(locale, "files_filter")} aria-label={t(locale, "files_filter")} />
        <span className="files-inline-count" title={selectedPath || workspaceLabel}>
          <Files size={13} aria-hidden="true" />
          <strong>{items.length.toLocaleString()}</strong>
        </span>
        {remainingCount || tree?.truncated ? (
          <button
            type="button"
            className="files-list-toggle"
            aria-expanded={filesExpanded}
            onClick={() => setFilesExpanded((value) => !value)}
            title={tree?.truncated ? filePanelText(locale, "truncated") : undefined}
          >
            <span>{filesExpanded ? reviewPanelText(locale, "collapse") : remainingCount ? reviewPanelText(locale, "remaining", remainingCount) : filePanelText(locale, "truncated")}</span>
            {filesExpanded ? <ChevronUp size={13} aria-hidden="true" /> : <ChevronDown size={13} aria-hidden="true" />}
          </button>
        ) : null}
      </div>

      <div className="files-list-shell">
        <div className="files-list-head">
          <span title={selectedPath || workspaceLabel}>{selectedPath ? fileNameLabel(selectedPath) : filePanelText(locale, "workspace")}</span>
          <small title={selectedPath ? (parentPathLabel(selectedPath) || workspaceLabel) : workspaceLabel}>
            {selectedPath ? (parentPathLabel(selectedPath) || workspaceLabel) : workspaceLabel}
          </small>
        </div>
        <div className={`inspector-list inspector-file-list ${filesExpanded ? "expanded" : ""}`} role="list" aria-label={t(locale, "files_title")}>
          {visibleItems.map((item) => (
            <button
              type="button"
              data-testid="project-file-row"
              className={`inspector-list-row file-list-row ${selectedPath === item.path ? "active" : ""}`}
              onClick={() => onSelectPath(item.path)}
              key={item.path}
              title={item.path}
            >
              <span className="file-list-copy">
                <strong>{fileNameLabel(item.path)}</strong>
                <small title={parentPathLabel(item.path) || item.path}>{parentPathLabel(item.path) || item.path}</small>
              </span>
              <small className="file-list-kind">{fileKindLabel(locale, item.kind)}</small>
            </button>
          ))}
          {!items.length ? <p className="muted compact-copy">{t(locale, "files_empty")}</p> : null}
        </div>
      </div>

      <FilePreviewCanvas
        locale={locale}
        project={project}
        preview={preview}
        mediaUrl={mediaUrl}
        previewError={previewError}
        mediaError={mediaError}
        selectedPath={selectedPath}
        selectedText={selectedText}
        fallbackDetail={fallbackDetail}
        loading={Boolean(previewLoading && selectedPath)}
        canOpenRaw={canOpenRaw}
      />
    </section>
  );
}
