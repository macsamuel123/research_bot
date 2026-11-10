import { describe, expect, it } from "vitest";

import nextConfig from "../next.config";

const RUN_TIMEOUT_SECONDS = 180;

describe("next.config", () => {
  it("disables compression so SSE streams through the proxy unbuffered", () => {
    expect(nextConfig.compress).toBe(false);
  });

  it("proxy timeout covers RUN_TIMEOUT_SECONDS + 30 s", () => {
    expect(nextConfig.experimental?.proxyTimeout).toBeGreaterThanOrEqual((RUN_TIMEOUT_SECONDS + 30) * 1000);
  });

  it("rewrites /api, /docs and /openapi.json to the api", async () => {
    const rewrites = await nextConfig.rewrites?.();
    expect(Array.isArray(rewrites)).toBe(true);
    const sources = (rewrites as { source: string }[]).map((r) => r.source);
    expect(sources).toEqual(["/api/:path*", "/docs", "/openapi.json"]);
  });
});
