export type LaunchIsolationReason =
  | "tauri"
  | "non_dev"
  | "trusted_query"
  | "explicit_bare_dev"
  | "non_loopback"
  | "blocked_loopback_dev";

export type LaunchIsolationDecision = {
  allowed: boolean;
  reason: LaunchIsolationReason;
};

export type LaunchIsolationOptions = {
  isDev: boolean;
  isTauri: boolean;
  allowBareDev?: boolean;
};

const TRUSTED_QUERY_PARAMS = new Set(["ab_session", "astrabridge_launch"]);

export function evaluateLaunchIsolation(href: string, options: LaunchIsolationOptions): LaunchIsolationDecision {
  if (options.isTauri) return { allowed: true, reason: "tauri" };
  if (!options.isDev) return { allowed: true, reason: "non_dev" };
  if (options.allowBareDev) return { allowed: true, reason: "explicit_bare_dev" };

  let url: URL;
  try {
    url = new URL(href);
  } catch {
    return { allowed: false, reason: "blocked_loopback_dev" };
  }

  if (!isLoopbackHttpUrl(url)) return { allowed: true, reason: "non_loopback" };
  for (const key of TRUSTED_QUERY_PARAMS) {
    const value = url.searchParams.get(key);
    if (value && value.trim()) return { allowed: true, reason: "trusted_query" };
  }
  return { allowed: false, reason: "blocked_loopback_dev" };
}

function isLoopbackHttpUrl(url: URL) {
  if (!["http:", "https:"].includes(url.protocol)) return false;
  const hostname = url.hostname.toLowerCase();
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]" || hostname === "::1";
}
