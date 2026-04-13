/**
 * Reverse proxy to FastAPI under /api/v1.
 *
 * Browser calls same-origin /api/v1/*; this handler forwards to BACKEND_INTERNAL_URL
 * so Docker can use http://backend:8000 while local dev uses 127.0.0.1:8000.
 * Env is read per request (no reliance on rewrite-time config).
 */

import type { NextRequest } from "next/server";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
]);

function backendOrigin(): string {
  const raw = process.env.BACKEND_INTERNAL_URL?.trim();
  if (raw) {
    return raw.replace(/\/$/, "");
  }
  return "http://127.0.0.1:8000";
}

function buildTarget(request: NextRequest, pathSegments: string[]): string {
  const suffix = pathSegments.length ? `/${pathSegments.join("/")}` : "";
  const url = new URL(request.url);
  return `${backendOrigin()}/api/v1${suffix}${url.search}`;
}

function forwardRequestHeaders(request: NextRequest): Headers {
  const out = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      out.append(key, value);
    }
  });
  return out;
}

function forwardResponseHeaders(src: Headers): Headers {
  const out = new Headers();
  src.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      out.append(key, value);
    }
  });
  return out;
}

/** Default cap for most API calls (avoid hung Node fetch). */
const UPSTREAM_FETCH_TIMEOUT_MS = 90_000;
/** AI assistant: OpenAI + tools often exceeds 90s; align with client `api.ts` and nginx `/api/` (600s). */
const UPSTREAM_AI_ASSISTANT_TIMEOUT_MS = 600_000;

function upstreamTimeoutMs(segments: string[]): number {
  if (segments.length > 0 && segments[0] === "ai-assistant") {
    return UPSTREAM_AI_ASSISTANT_TIMEOUT_MS;
  }
  return UPSTREAM_FETCH_TIMEOUT_MS;
}

function upstreamTimeoutSignal(segments: string[]): AbortSignal | undefined {
  const ctor = AbortSignal as unknown as { timeout?: (ms: number) => AbortSignal };
  const ms = upstreamTimeoutMs(segments);
  return ctor.timeout?.(ms);
}

async function proxy(request: NextRequest, path: string[] | undefined): Promise<Response> {
  const segments = path ?? [];
  const targetUrl = buildTarget(request, segments);
  const headers = forwardRequestHeaders(request);
  const timeoutMs = upstreamTimeoutMs(segments);

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
    signal: upstreamTimeoutSignal(segments),
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    const buf = await request.arrayBuffer();
    if (buf.byteLength > 0) {
      init.body = buf;
    }
  }

  let upstream: Response;
  try {
    upstream = await fetch(targetUrl, init);
  } catch (e) {
    const aborted =
      typeof e === "object" &&
      e !== null &&
      "name" in e &&
      (e as { name: string }).name === "AbortError";
    const msg = aborted
      ? `upstream timed out after ${timeoutMs / 1000}s`
      : e instanceof Error
        ? e.message
        : "upstream fetch failed";
    return new Response(
      JSON.stringify({
        error: {
          code: aborted ? "PROXY_UPSTREAM_TIMEOUT" : "PROXY_UPSTREAM_ERROR",
          message: `Cannot reach API at ${backendOrigin()}: ${msg}`,
        },
      }),
      { status: aborted ? 504 : 502, headers: { "Content-Type": "application/json" } },
    );
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: forwardResponseHeaders(upstream.headers),
  });
}

export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return proxy(request, path);
}

export async function POST(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return proxy(request, path);
}

export async function PUT(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return proxy(request, path);
}

export async function PATCH(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return proxy(request, path);
}

export async function DELETE(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return proxy(request, path);
}

export async function OPTIONS(
  request: NextRequest,
  ctx: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  return proxy(request, path);
}
