import type { NextConfig } from "next";

// Proxy target for /api, /docs and /openapi.json (same-origin session cookie).
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";
// Must cover RUN_TIMEOUT_SECONDS (180) + 30 s so SSE responses are not cut by the proxy.
const PROXY_TIMEOUT_MS = 210_000;

const nextConfig: NextConfig = {
  compress: false,
  devIndicators: false,
  experimental: { proxyTimeout: PROXY_TIMEOUT_MS },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${apiInternalUrl}/api/:path*` },
      { source: "/docs", destination: `${apiInternalUrl}/docs` },
      { source: "/openapi.json", destination: `${apiInternalUrl}/openapi.json` },
    ];
  },
};

export default nextConfig;
