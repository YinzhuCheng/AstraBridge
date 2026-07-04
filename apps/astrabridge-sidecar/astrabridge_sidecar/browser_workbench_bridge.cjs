const fs = require("fs");
const path = require("path");
const readline = require("readline");

let playwright;

function tryRequireFromPnpm(baseName) {
  const pnpmRoot = path.join(process.cwd(), "node_modules", ".pnpm");
  if (!fs.existsSync(pnpmRoot)) return null;
  const match = fs.readdirSync(pnpmRoot).find((name) => name.startsWith(baseName + "@"));
  if (!match) return null;
  const target = path.join(pnpmRoot, match, "node_modules", baseName);
  if (!fs.existsSync(target)) return null;
  return require(target);
}

try {
  playwright = require("playwright");
} catch (error) {
  try {
    playwright = require("playwright-core");
  } catch (coreError) {
    playwright = tryRequireFromPnpm("playwright") || tryRequireFromPnpm("playwright-core");
    if (!playwright) {
      process.stdout.write(JSON.stringify({ ok: false, fatal: true, error: String(coreError.message || coreError) }) + "\n");
      process.exit(1);
    }
  }
}

async function launchBrowser() {
  const candidates = [
    null,
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  ];
  const failures = [];
  for (const candidate of candidates) {
    try {
      if (candidate && !fs.existsSync(candidate)) continue;
      const options = { headless: true };
      if (candidate) options.executablePath = candidate;
      return await playwright.chromium.launch(options);
    } catch (error) {
      failures.push(`${candidate || "playwright-chromium"}: ${String(error.message || error).slice(0, 200)}`);
    }
  }
  throw new Error(`No browser runtime available. ${failures.join(" | ")}`);
}

function clampNumber(value, min, max, fallback) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}

const DESKTOP_VIEWPORT = { width: 1365, height: 900 };
const MOBILE_VIEWPORT = { width: 390, height: 844 };
const VIEWPORTS = {
  desktop: DESKTOP_VIEWPORT,
  mobile: MOBILE_VIEWPORT,
};
const CHROME_MAJOR = "126";
const CHROME_FULL_VERSION = "126.0.0.0";
const DESKTOP_USER_AGENT =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const MOBILE_USER_AGENT =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36";
const CHROME_BRANDS = [
  { brand: "Chromium", version: CHROME_MAJOR },
  { brand: "Google Chrome", version: CHROME_MAJOR },
  { brand: "Not.A/Brand", version: "99" },
];
const DESKTOP_USER_AGENT_METADATA = {
  brands: CHROME_BRANDS,
  fullVersionList: CHROME_BRANDS.map((item) => ({ ...item, version: item.version === CHROME_MAJOR ? CHROME_FULL_VERSION : item.version })),
  platform: "Windows",
  platformVersion: "10.0.0",
  architecture: "x86",
  model: "",
  mobile: false,
  bitness: "64",
  wow64: false,
};
const MOBILE_USER_AGENT_METADATA = {
  brands: CHROME_BRANDS,
  fullVersionList: CHROME_BRANDS.map((item) => ({ ...item, version: item.version === CHROME_MAJOR ? CHROME_FULL_VERSION : item.version })),
  platform: "Android",
  platformVersion: "14",
  architecture: "arm",
  model: "Pixel 8",
  mobile: true,
  bitness: "64",
  wow64: false,
};
let browser = null;
let context = null;
let page = null;
let cdp = null;
let role = "Browser";
let sessionId = "browser";
let outputPath = "";
let lastError = null;
let layoutMode = "desktop";
let layoutReason = "desktop";
let mobileStrategy = "desktop_viewport";
let lastState = {
  id: sessionId,
  role,
  title: "AstraBridge Browser - Browser",
  page_title: "",
  url: "",
  status: "idle",
  error: null,
  preview_mode: "remote",
  viewport_width: DESKTOP_VIEWPORT.width,
  viewport_height: DESKTOP_VIEWPORT.height,
  layout_mode: layoutMode,
  layout_reason: layoutReason,
  mobile_optimized: null,
  has_viewport_meta: null,
  horizontal_overflow_ratio: null,
  wide_element_count: null,
  mobile_strategy: "desktop_viewport",
  responsive_fit_score: null,
  can_go_back: false,
  can_go_forward: false,
  loading: false,
  updated_at: new Date().toISOString(),
};

function nowIso() {
  return new Date().toISOString();
}

function updateState(patch) {
  lastState = {
    ...lastState,
    ...patch,
    updated_at: nowIso(),
  };
}

async function attachPage(nextPage) {
  page = nextPage;
  page.on("load", async () => {
    try {
      updateState({ loading: false, page_title: await page.title(), url: page.url() });
      await refreshHistoryFlags();
    } catch (_error) {
      // ignore async listener failures
    }
  });
  page.on("domcontentloaded", async () => {
    try {
      updateState({ loading: false, page_title: await page.title(), url: page.url() });
      await refreshHistoryFlags();
    } catch (_error) {
      // ignore async listener failures
    }
  });
  page.on("popup", async (popup) => {
    await attachPage(popup);
  });
  page.on("pageerror", (error) => {
    lastError = String(error.message || error).slice(0, 300);
    updateState({ error: lastError });
  });
  if (context?.newCDPSession) {
    try {
      cdp = await context.newCDPSession(page);
    } catch (_error) {
      cdp = null;
    }
  }
}

async function ensureRuntime() {
  if (browser) return;
  browser = await launchBrowser();
  context = await browser.newContext({
    viewport: DESKTOP_VIEWPORT,
    userAgent: DESKTOP_USER_AGENT,
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: false,
    ignoreHTTPSErrors: true,
  });
  const firstPage = await context.newPage();
  await attachPage(firstPage);
}

function normalizeLayoutMode(value) {
  const mode = String(value || "").trim().toLowerCase();
  return mode === "mobile" ? "mobile" : "desktop";
}

function activeViewport() {
  return VIEWPORTS[layoutMode] || DESKTOP_VIEWPORT;
}

function normalizeMobileStrategy(strategy, mode) {
  const raw = String(strategy || "").trim();
  if (raw) return raw;
  return mode === "mobile" ? "mobile_user_agent_viewport" : "desktop_viewport";
}

async function applyUserAgentOverride(mode) {
  if (!cdp) return;
  const mobile = mode === "mobile";
  await cdp.send("Network.setUserAgentOverride", {
    userAgent: mobile ? MOBILE_USER_AGENT : DESKTOP_USER_AGENT,
    acceptLanguage: "en-US,en;q=0.9",
    platform: mobile ? "Android" : "Windows",
    userAgentMetadata: mobile ? MOBILE_USER_AGENT_METADATA : DESKTOP_USER_AGENT_METADATA,
  });
}

async function applyLayoutMode(nextMode, reason, strategy) {
  const mode = normalizeLayoutMode(nextMode);
  const viewport = VIEWPORTS[mode] || DESKTOP_VIEWPORT;
  const changed = layoutMode !== mode;
  layoutMode = mode;
  layoutReason = String(reason || (mode === "mobile" ? "tall panel mobile emulation" : "desktop panel")).slice(0, 160);
  mobileStrategy = normalizeMobileStrategy(strategy, mode);
  if (page) {
    await page.setViewportSize(viewport);
    if (cdp) {
      try {
        if (mode === "mobile") {
          await cdp.send("Emulation.setDeviceMetricsOverride", {
            width: viewport.width,
            height: viewport.height,
            deviceScaleFactor: 3,
            mobile: true,
            screenWidth: viewport.width,
            screenHeight: viewport.height,
            screenOrientation: { type: "portraitPrimary", angle: 0 },
          });
          await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });
          await applyUserAgentOverride("mobile");
        } else {
          await cdp.send("Emulation.clearDeviceMetricsOverride");
          await cdp.send("Emulation.setTouchEmulationEnabled", { enabled: false });
          await applyUserAgentOverride("desktop");
        }
      } catch (_error) {
        // Playwright viewport sizing still gives the page a responsive target when CDP emulation is unavailable.
      }
    }
  }
  updateState({
    layout_mode: layoutMode,
    layout_reason: layoutReason,
    viewport_width: viewport.width,
    viewport_height: viewport.height,
    mobile_strategy: mobileStrategy,
  });
  return changed;
}

async function refreshHistoryFlags() {
  if (!page) return;
  let canGoBack = false;
  let canGoForward = false;
  if (cdp) {
    try {
      const history = await cdp.send("Page.getNavigationHistory");
      const index = Number(history.currentIndex || 0);
      const entries = Array.isArray(history.entries) ? history.entries : [];
      canGoBack = index > 0;
      canGoForward = index < entries.length - 1;
    } catch (_error) {
      canGoBack = false;
      canGoForward = false;
    }
  } else {
    try {
      const historyLength = await page.evaluate(() => window.history.length);
      canGoBack = Number(historyLength || 0) > 1;
    } catch (_error) {
      canGoBack = false;
    }
  }
  updateState({ can_go_back: canGoBack, can_go_forward: canGoForward });
}

async function capture() {
  if (!page || !outputPath) return;
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  const fit = await analyzePageFit();
  if (cdp) {
    try {
      const result = await cdp.send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(outputPath, Buffer.from(String(result.data || ""), "base64"));
      updateState({ screenshot_path: outputPath, page_title: await page.title(), url: page.url(), ...fit });
      return;
    } catch (_error) {
      // Fall back to Playwright screenshot below.
    }
  }
  await page.screenshot({ path: outputPath, fullPage: false, timeout: 5000, animations: "disabled" });
  updateState({ screenshot_path: outputPath, page_title: await page.title(), url: page.url(), ...fit });
}

async function analyzePageFit() {
  if (!page) {
    return {
      mobile_optimized: null,
      has_viewport_meta: null,
      horizontal_overflow_ratio: null,
      wide_element_count: null,
    };
  }
  try {
    const result = await page.evaluate(() => {
      const doc = document.documentElement;
      const body = document.body;
      const clientWidth = Math.max(doc?.clientWidth || 0, window.innerWidth || 0, 1);
      const scrollWidth = Math.max(doc?.scrollWidth || 0, body?.scrollWidth || 0, clientWidth);
      const overflowRatio = scrollWidth / clientWidth;
      const hasViewportMeta = Boolean(document.querySelector('meta[name="viewport"]'));
      const elements = Array.from(body?.querySelectorAll("*") || []).slice(0, 800);
      let wideElementCount = 0;
      for (const element of elements) {
        const rect = element.getBoundingClientRect();
        if (rect.height > 8 && rect.width > clientWidth * 1.18) {
          wideElementCount += 1;
          if (wideElementCount > 8) break;
        }
      }
      return {
        has_viewport_meta: hasViewportMeta,
        horizontal_overflow_ratio: Math.round(overflowRatio * 100) / 100,
        wide_element_count: wideElementCount,
        responsive_fit_score: Math.max(0, Math.min(100, Math.round((1 / Math.max(1, overflowRatio)) * 100) - wideElementCount * 8)),
        mobile_optimized: hasViewportMeta && overflowRatio <= 1.12 && wideElementCount <= 2,
      };
    });
    return {
      has_viewport_meta: Boolean(result.has_viewport_meta),
      horizontal_overflow_ratio: Number(result.horizontal_overflow_ratio || 1),
      wide_element_count: Number(result.wide_element_count || 0),
      responsive_fit_score: Number(result.responsive_fit_score ?? 0),
      mobile_optimized: layoutMode === "mobile" ? Boolean(result.mobile_optimized) : lastState.mobile_optimized,
      mobile_strategy: mobileStrategy,
    };
  } catch (_error) {
    return {
      mobile_optimized: layoutMode === "mobile" ? false : lastState.mobile_optimized,
      has_viewport_meta: null,
      horizontal_overflow_ratio: null,
      wide_element_count: null,
      responsive_fit_score: null,
      mobile_strategy: mobileStrategy,
    };
  }
}

async function settleAfterAction() {
  if (!page) return;
  try {
    await page.waitForLoadState("domcontentloaded", { timeout: 5000 });
  } catch (_error) {
    // page did not navigate; continue
  }
  await page.waitForTimeout(220);
  await refreshHistoryFlags();
  await capture();
}

async function navigate(url) {
  if (!page) throw new Error("Browser page is not ready.");
  updateState({ loading: true, status: "navigating", error: null, url });
  lastError = null;
  let navigationError = null;
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
  } catch (error) {
    navigationError = String(error.message || error).slice(0, 300);
  }
  const currentUrl = page.url();
  const title = await page.title().catch(() => "");
  if (navigationError && (!currentUrl || currentUrl === "about:blank" || currentUrl.startsWith("chrome-error://"))) {
    lastError = navigationError;
    updateState({ status: "error", loading: false, error: navigationError, url: currentUrl || url, page_title: title });
    await capture().catch(() => {});
    return;
  }
  updateState({ status: "open", loading: false, error: null, url: currentUrl || url, page_title: title });
  await settleAfterAction();
}

async function sessionSnapshot() {
  if (page) {
    updateState({
      page_title: await page.title(),
      url: page.url(),
      error: lastError,
    });
    await refreshHistoryFlags();
  }
  return { ...lastState };
}

async function handleCreate(params) {
  await ensureRuntime();
  role = String(params.role || role || "Browser").trim() || "Browser";
  sessionId = String(params.session_id || sessionId || "browser");
  outputPath = String(params.screenshot_path || outputPath || "");
  updateState({
    id: sessionId,
    role,
    title: `AstraBridge Browser - ${role}`,
    status: "open",
    error: null,
    preview_mode: "remote",
  });
  await applyLayoutMode(params.layout_mode, params.layout_reason, params.mobile_strategy);
  await navigate(String(params.url || ""));
  return sessionSnapshot();
}

async function handleNavigate(params) {
  outputPath = String(params.screenshot_path || outputPath || "");
  if (params.layout_mode) {
    await applyLayoutMode(params.layout_mode, params.layout_reason, params.mobile_strategy);
  }
  await navigate(String(params.url || ""));
  return sessionSnapshot();
}

async function handleLayout(params) {
  outputPath = String(params.screenshot_path || outputPath || "");
  const changed = await applyLayoutMode(params.layout_mode, params.layout_reason, params.mobile_strategy);
  if (changed && page) {
    const currentUrl = page.url();
    if (currentUrl && currentUrl !== "about:blank" && !currentUrl.startsWith("chrome-error://")) {
      updateState({ loading: true, status: "navigating", error: null });
      await page.reload({ waitUntil: "domcontentloaded", timeout: 20000 }).catch(() => null);
    }
  }
  updateState({ loading: false, status: "open", error: lastError });
  await settleAfterAction();
  return sessionSnapshot();
}

async function handleAction(params) {
  if (!page) throw new Error("Browser page is not ready.");
  outputPath = String(params.screenshot_path || outputPath || "");
  const action = String(params.action || "");
  lastError = null;
  updateState({ loading: true, error: null });
  if (action === "click") {
    const viewport = activeViewport();
    const x = clampNumber(params.x, 0, viewport.width, viewport.width / 2);
    const y = clampNumber(params.y, 0, viewport.height, viewport.height / 2);
    await page.mouse.click(x, y);
  } else if (action === "double_click") {
    const viewport = activeViewport();
    const x = clampNumber(params.x, 0, viewport.width, viewport.width / 2);
    const y = clampNumber(params.y, 0, viewport.height, viewport.height / 2);
    await page.mouse.click(x, y, { clickCount: 2 });
  } else if (action === "scroll") {
    const deltaX = clampNumber(params.delta_x, -3000, 3000, 0);
    const deltaY = clampNumber(params.delta_y, -3000, 3000, 0);
    await page.mouse.wheel(deltaX, deltaY);
  } else if (action === "back") {
    await page.goBack({ waitUntil: "domcontentloaded", timeout: 15000 }).catch(() => null);
  } else if (action === "forward") {
    await page.goForward({ waitUntil: "domcontentloaded", timeout: 15000 }).catch(() => null);
  } else if (action === "reload") {
    await page.reload({ waitUntil: "domcontentloaded", timeout: 20000 });
  } else if (action === "press") {
    const key = String(params.key || "").trim();
    if (!key) throw new Error("Key is required.");
    await page.keyboard.press(key);
  } else if (action === "type_text") {
    await page.keyboard.type(String(params.text || ""));
  } else {
    throw new Error(`Unsupported browser action: ${action}`);
  }
  updateState({ loading: false, status: "open", error: null });
  await settleAfterAction();
  return sessionSnapshot();
}

async function handleSnapshot(params) {
  if (params && params.screenshot_path) {
    outputPath = String(params.screenshot_path || outputPath || "");
  }
  if (page) {
    await settleAfterAction();
  }
  return sessionSnapshot();
}

async function handleClose() {
  try {
    if (browser) {
      await browser.close();
    }
  } finally {
    browser = null;
    context = null;
    page = null;
    cdp = null;
    updateState({ status: "closed", loading: false });
  }
  return sessionSnapshot();
}

async function dispatch(message) {
  const id = Number(message.id || 0);
  const method = String(message.method || "");
  const params = message.params || {};
  try {
    let session;
    if (method === "create") {
      session = await handleCreate(params);
    } else if (method === "navigate") {
      session = await handleNavigate(params);
    } else if (method === "layout") {
      session = await handleLayout(params);
    } else if (method === "action") {
      session = await handleAction(params);
    } else if (method === "snapshot") {
      session = await handleSnapshot(params);
    } else if (method === "close") {
      session = await handleClose();
    } else {
      throw new Error(`Unsupported method: ${method}`);
    }
    process.stdout.write(JSON.stringify({ id, ok: true, session }) + "\n");
    if (method === "close") {
      process.exit(0);
    }
  } catch (error) {
    lastError = String(error.message || error).slice(0, 300);
    updateState({ loading: false, status: "error", error: lastError });
    process.stdout.write(JSON.stringify({ id, ok: false, error: lastError, session: { ...lastState } }) + "\n");
  }
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on("line", (line) => {
  const trimmed = String(line || "").trim();
  if (!trimmed) return;
  let message;
  try {
    message = JSON.parse(trimmed);
  } catch (error) {
    process.stdout.write(JSON.stringify({ id: 0, ok: false, error: `Invalid JSON: ${String(error.message || error)}` }) + "\n");
    return;
  }
  void dispatch(message);
});

process.on("SIGINT", async () => {
  try {
    if (browser) await browser.close();
  } catch (_error) {
    // ignore
  }
  process.exit(0);
});
