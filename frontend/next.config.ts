import type { NextConfig } from "next";

/**
 * API proxy: `src/app/api/v1/[[...path]]/route.ts` forwards to BACKEND_INTERNAL_URL.
 * Rewrites are not used so Docker/local env is applied per request on the server.
 */

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  /** Fresh HTML after deploy; `_next/static` stays immutable (matched first). */
  async headers() {
    return [
      {
        source: "/_next/static/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }],
      },
      {
        source: "/:path*",
        headers: [
          {
            key: "Cache-Control",
            value: "private, no-cache, no-store, max-age=0, must-revalidate",
          },
        ],
      },
    ];
  },
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "9000" },
      { protocol: "http", hostname: "minio", port: "9000" },
    ],
  },
};

export default nextConfig;
