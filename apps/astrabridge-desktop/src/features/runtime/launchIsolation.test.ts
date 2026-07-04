import { describe, expect, it } from "vitest";
import { evaluateLaunchIsolation } from "./launchIsolation";

describe("evaluateLaunchIsolation", () => {
  it("allows Tauri even when devUrl is a fixed loopback port", () => {
    expect(evaluateLaunchIsolation("http://127.0.0.1:5173/", { isDev: true, isTauri: true })).toEqual({
      allowed: true,
      reason: "tauri",
    });
  });

  it("blocks bare loopback dev URLs before rendering product UI", () => {
    expect(evaluateLaunchIsolation("http://127.0.0.1:5173/", { isDev: true, isTauri: false })).toEqual({
      allowed: false,
      reason: "blocked_loopback_dev",
    });
  });

  it("blocks browser dogfood URLs that only select a sidecar", () => {
    expect(
      evaluateLaunchIsolation("http://127.0.0.1:5173/?sidecar=http%3A%2F%2F127.0.0.1%3A8792", {
        isDev: true,
        isTauri: false,
      }),
    ).toEqual({
      allowed: false,
      reason: "blocked_loopback_dev",
    });
  });

  it("blocks smoke URLs without an explicit launch marker", () => {
    expect(evaluateLaunchIsolation("http://127.0.0.1:5173/?smoke=1", { isDev: true, isTauri: false })).toEqual({
      allowed: false,
      reason: "blocked_loopback_dev",
    });
  });

  it("allows explicitly marked browser dogfood URLs", () => {
    expect(
      evaluateLaunchIsolation("http://127.0.0.1:5173/?astrabridge_launch=dogfood&sidecar=http%3A%2F%2F127.0.0.1%3A8792&smoke=1", {
        isDev: true,
        isTauri: false,
      }),
    ).toEqual({
      allowed: true,
      reason: "trusted_query",
    });
  });

  it("keeps production web builds reachable", () => {
    expect(evaluateLaunchIsolation("http://127.0.0.1:5173/", { isDev: false, isTauri: false })).toEqual({
      allowed: true,
      reason: "non_dev",
    });
  });
});
