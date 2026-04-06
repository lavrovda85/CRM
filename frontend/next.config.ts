import type { NextConfig } from "next";

/**
 * API proxy: `src/app/api/v1/[[...path]]/route.ts` forwards to BACKEND_INTERNAL_URL.
 * Rewrites are not used so Docker/local env is applied per request on the server.
 */

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "9000" },
      { protocol: "http", hostname: "minio", port: "9000" },
    ],
  },
};

export default nextConfig;
