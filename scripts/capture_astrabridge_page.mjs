#!/usr/bin/env node
import fs from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..");
const desktopRequire = createRequire(path.join(repoRoot, "apps", "astrabridge-desktop", "package.json"));

function usage() {
  return [
    "Usage:",
    "  node scripts/capture_astrabridge_page.mjs --url <url> --out <png> [--report <json>] [--wait-ms 1000] [--viewport-width 1365] [--viewport-height 900] [--actions-json <json> | --actions-file <json>] [--expect-text <text>]",
    "",
    "Captures AstraBridge through an isolated headless browser, independent of the desktop foreground window.",
  ].join("\n");
}

function parseArgs(argv) {
  const parsed = {
    url: "",
    out: "",
    report: "",
    waitMs: 1000,
    navigationTimeoutMs: 20000,
    viewportWidth: 1365,
    viewportHeight: 900,
    fullPage: true,
    actions: [],
    expectTexts: [],
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => {
      index += 1;
      if (index >= argv.length) throw new Error(`Missing value for ${arg}`);
      return argv[index];
    };
    if (arg === "--url") parsed.url = next();
    else if (arg === "--out") parsed.out = next();
    else if (arg === "--report") parsed.report = next();
    else if (arg === "--wait-ms") parsed.waitMs = Number(next()) || 0;
    else if (arg === "--navigation-timeout-ms") parsed.navigationTimeoutMs = Number(next()) || parsed.navigationTimeoutMs;
    else if (arg === "--viewport-width") parsed.viewportWidth = Number(next()) || parsed.viewportWidth;
    else if (arg === "--viewport-height") parsed.viewportHeight = Number(next()) || parsed.viewportHeight;
    else if (arg === "--full-page") parsed.fullPage = String(next()).toLowerCase() !== "false";
    else if (arg === "--actions-json") parsed.actions = JSON.parse(next());
    else if (arg === "--actions-file") parsed.actions = JSON.parse(awaitReadText(next()));
    else if (arg === "--expect-text") parsed.expectTexts.push(next());
    else if (arg === "--help" || arg === "-h") {
      console.log(usage());
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (!parsed.url) throw new Error("--url is required");
  if (!parsed.out) throw new Error("--out is required");
  if (!Array.isArray(parsed.actions)) throw new Error("--actions-json must decode to an array");
  return parsed;
}

function awaitReadText(filePath) {
  return desktopRequire("fs").readFileSync(path.resolve(filePath), "utf8").replace(/^\uFEFF/, "");
}

function loadPlaywright() {
  try {
    return desktopRequire("playwright");
  } catch (_error) {
    return desktopRequire("playwright-core");
  }
}

async function launchBrowser(playwright) {
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
      if (candidate && !existsSync(candidate)) continue;
      const options = { headless: true };
      if (candidate) options.executablePath = candidate;
      const browser = await playwright.chromium.launch(options);
      return { browser, executable: candidate || "playwright-chromium" };
    } catch (error) {
      failures.push(`${candidate || "playwright-chromium"}: ${String(error?.message || error).slice(0, 240)}`);
    }
  }
  throw new Error(`No browser runtime available. ${failures.join(" | ")}`);
}

async function runAction(page, action) {
  const type = String(action?.type || "");
  const timeout = Number(action?.timeout_ms || 3000);
  if (type === "wait_ms") {
    await page.waitForTimeout(Math.min(Math.max(Number(action.ms || 0), 0), 15000));
    return { type, ok: true, ms: Number(action.ms || 0) };
  }
  if (type === "click_text") {
    const text = String(action.text || "");
    await page.getByText(text, { exact: false }).first().click({ timeout });
    return { type, ok: true, text };
  }
  if (type === "click_selector") {
    const selector = String(action.selector || "");
    await page.locator(selector).first().click({ timeout });
    return { type, ok: true, selector };
  }
  if (type === "fill_selector") {
    const selector = String(action.selector || "");
    const value = String(action.value || "");
    await page.locator(selector).first().fill(value, { timeout });
    return { type, ok: true, selector, value_preview: value.slice(0, 80) };
  }
  if (type === "select_selector") {
    const selector = String(action.selector || "");
    const value = String(action.value || "");
    await page.locator(selector).first().selectOption(value, { timeout });
    return { type, ok: true, selector, value };
  }
  if (type === "expect_text") {
    const text = String(action.text || "");
    await page.getByText(text, { exact: false }).first().waitFor({ state: "visible", timeout });
    return { type, ok: true, text };
  }
  if (type === "scroll_to_text") {
    const text = String(action.text || "");
    const locator = page.getByText(text, { exact: false }).first();
    await locator.waitFor({ state: "attached", timeout });
    await locator.scrollIntoViewIfNeeded({ timeout });
    return { type, ok: true, text };
  }
  if (type === "scroll_y") {
    const deltaY = Number(action.delta_y || action.pixels || 0);
    await page.mouse.wheel(0, deltaY);
    return { type, ok: true, delta_y: deltaY };
  }
  if (type === "expect_selector") {
    const selector = String(action.selector || "");
    await page.locator(selector).first().waitFor({ state: "visible", timeout });
    return { type, ok: true, selector };
  }
  if (type === "scroll_selector_into_view") {
    const selector = String(action.selector || "");
    await page.locator(selector).first().scrollIntoViewIfNeeded({ timeout });
    return { type, ok: true, selector };
  }
  throw new Error(`Unsupported action type: ${type}`);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const playwright = loadPlaywright();
  const launched = await launchBrowser(playwright);
  const browser = launched.browser;
  const page = await browser.newPage({ viewport: { width: args.viewportWidth, height: args.viewportHeight }, deviceScaleFactor: 1 });
  const consoleIssues = [];
  const requestFailures = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleIssues.push(`${message.type()}: ${message.text()}`.slice(0, 300));
    }
  });
  page.on("pageerror", (error) => consoleIssues.push(`pageerror: ${String(error?.message || error)}`.slice(0, 300)));
  page.on("requestfailed", (request) => {
    requestFailures.push({
      url: String(request.url() || "").slice(0, 300),
      method: String(request.method() || "").slice(0, 32),
      resource_type: String(request.resourceType() || "").slice(0, 40),
      error_text: String(request.failure()?.errorText || "request failed").slice(0, 200),
    });
  });

  const startedAt = new Date().toISOString();
  const actionResults = [];
  let screenshotStatus = "not_captured";
  let status = null;
  try {
    const response = await page.goto(args.url, { waitUntil: "domcontentloaded", timeout: args.navigationTimeoutMs });
    status = response ? response.status() : null;
    for (const action of args.actions) {
      actionResults.push(await runAction(page, action));
    }
    if (args.waitMs > 0) {
      await page.waitForTimeout(Math.min(Math.max(args.waitMs, 0), 30000));
    }
    for (const text of args.expectTexts) {
      await page.getByText(text, { exact: false }).first().waitFor({ state: "visible", timeout: 5000 });
    }
    await fs.mkdir(path.dirname(path.resolve(args.out)), { recursive: true });
    try {
      await page.screenshot({ path: args.out, fullPage: args.fullPage });
      screenshotStatus = args.fullPage ? "captured_full_page" : "captured_viewport";
    } catch (error) {
      consoleIssues.push(`screenshot-fullpage: ${String(error?.message || error).slice(0, 300)}`);
      await page.screenshot({ path: args.out, fullPage: false });
      screenshotStatus = "captured_viewport_fallback";
    }
    const bodyText = await page.locator("body").innerText({ timeout: 5000 }).catch(() => "");
    const report = {
      ok: true,
      schema_version: "astrabridge-focus-independent-page-capture-v1",
      capture_mode: "headless_playwright",
      capture_scope: "page_not_desktop",
      started_at: startedAt,
      completed_at: new Date().toISOString(),
      url: args.url,
      final_url: page.url(),
      http_status: status,
      viewport: {
        width: args.viewportWidth,
        height: args.viewportHeight,
      },
      screenshot_path: path.resolve(args.out),
      screenshot_status: screenshotStatus,
      browser_executable: launched.executable,
      action_results: actionResults,
      expect_texts: args.expectTexts,
      text_excerpt: bodyText.slice(0, 2000),
      console_issues: consoleIssues.slice(0, 20),
      request_failures: requestFailures.slice(0, 20),
    };
    if (args.report) {
      await fs.mkdir(path.dirname(path.resolve(args.report)), { recursive: true });
      await fs.writeFile(args.report, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    }
    console.log(JSON.stringify(report));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(JSON.stringify({ ok: false, error: String(error?.message || error) }));
  process.exitCode = 1;
});
