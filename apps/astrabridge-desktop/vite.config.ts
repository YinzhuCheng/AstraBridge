import http, { type IncomingMessage } from "node:http";
import https from "node:https";

import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const SIDECAR_PROXY_PREFIX = "/__astrabridge_proxy__";
const REQUEST_HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "x-astrabridge-sidecar-base",
]);

const RESPONSE_HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function normalizeSidecarBase(value: string | null | undefined) {
  const trimmed = value?.trim();
  if (!trimmed) return "";
  try {
    const url = new URL(trimmed);
    if (!["http:", "https:"].includes(url.protocol)) return "";
    url.pathname = url.pathname.replace(/\/+$/, "");
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  } catch {
    return "";
  }
}

function astrabridgeSidecarProxyPlugin(): Plugin {
  return {
    name: "astrabridge-sidecar-proxy",
    configureServer(server) {
      const handle = async (req: Parameters<typeof server.middlewares.use>[0], res: Parameters<typeof server.middlewares.use>[1], next: Parameters<typeof server.middlewares.use>[2]) => {
        const rawUrl = req.url ?? "";
        if (!rawUrl.startsWith(SIDECAR_PROXY_PREFIX)) {
          next();
          return;
        }
        try {
          const incomingUrl = new URL(rawUrl, "http://127.0.0.1");
          const targetBase = normalizeSidecarBase(
            (Array.isArray(req.headers["x-astrabridge-sidecar-base"])
              ? req.headers["x-astrabridge-sidecar-base"][0]
              : req.headers["x-astrabridge-sidecar-base"]) ?? incomingUrl.searchParams.get("__sidecar"),
          );
          if (!targetBase) {
            res.statusCode = 400;
            res.setHeader("Content-Type", "application/json; charset=utf-8");
            res.end(JSON.stringify({ error: "Missing or invalid AstraBridge sidecar target." }));
            return;
          }
          incomingUrl.searchParams.delete("__sidecar");
          const upstreamUrl = new URL(incomingUrl.pathname.slice(SIDECAR_PROXY_PREFIX.length) || "/", `${targetBase}/`);
          upstreamUrl.search = incomingUrl.searchParams.toString() ? `?${incomingUrl.searchParams.toString()}` : "";
          const headers: Record<string, string> = {};
          for (const [key, value] of Object.entries(req.headers)) {
            const lowered = key.toLowerCase();
            if (REQUEST_HOP_BY_HOP_HEADERS.has(lowered) || value == null) continue;
            headers[key] = Array.isArray(value) ? value.join(", ") : value;
          }
          const upstreamTransport = upstreamUrl.protocol === "https:" ? https : http;
          const upstreamRequest = upstreamTransport.request(upstreamUrl, {
            method: req.method,
            headers,
          });
          req.on("aborted", () => upstreamRequest.destroy());
          req.on("close", () => {
            if (!req.complete) {
              upstreamRequest.destroy();
            }
          });
          const upstreamResponse = await new Promise<IncomingMessage>((resolve, reject) => {
            upstreamRequest.on("response", resolve);
            upstreamRequest.on("error", reject);
            if (!["GET", "HEAD"].includes((req.method ?? "GET").toUpperCase())) {
              req.pipe(upstreamRequest);
            } else {
              upstreamRequest.end();
            }
          });
          res.statusCode = upstreamResponse.statusCode ?? 502;
          for (const [key, value] of Object.entries(upstreamResponse.headers)) {
            if (value == null || RESPONSE_HOP_BY_HOP_HEADERS.has(key.toLowerCase())) continue;
            res.setHeader(key, value);
          }
          upstreamResponse.pipe(res);
        } catch (error) {
          res.statusCode = 502;
          res.setHeader("Content-Type", "application/json; charset=utf-8");
          res.end(
            JSON.stringify({
              error: error instanceof Error ? error.message : String(error),
            }),
          );
        }
      };
      (server.middlewares.stack as Array<{ route: string; handle: typeof handle }>).unshift({
        route: "",
        handle,
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), astrabridgeSidecarProxyPlugin()],
  clearScreen: false,
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
