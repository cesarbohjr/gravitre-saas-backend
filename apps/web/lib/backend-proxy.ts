/**
 * FE-10/FE-11: Server-only proxy to FastAPI. Never log tokens.
 * Returns 500 if FASTAPI_BASE_URL missing; 503 if backend fetch fails.
 */
import { NextRequest, NextResponse } from "next/server";

const BASE = process.env.FASTAPI_BASE_URL?.replace(/\/$/, "");

function buildHeaders(request: NextRequest): Record<string, string> {
  const authHeader = request.headers.get("authorization") ?? "";
  const envHeader = request.headers.get("x-environment") ?? "";
  return {
    Authorization: authHeader,
    "Content-Type": "application/json",
    ...(envHeader ? { "X-Environment": envHeader } : {}),
  };
}

/** FE-11: Proxy GET /api/audit with query string. Same error semantics. */
export async function proxyAuditToBackend(
  request: NextRequest,
  queryString: string
): Promise<NextResponse> {
  if (!BASE) {
    return NextResponse.json(
      { detail: "Backend not configured" },
      { status: 500 }
    );
  }
  const suffix = queryString.startsWith("?") ? queryString : `?${queryString}`;
  const url = `${BASE}/api/audit${suffix}`;
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: buildHeaders(request),
      cache: "no-store",
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      return NextResponse.json(data?.detail ?? data, { status: res.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 503 }
    );
  }
}

export async function proxyToBackend(
  request: NextRequest,
  path: string,
  options: { method: "GET" | "POST"; body?: string } = { method: "GET" }
): Promise<NextResponse> {
  if (!BASE) {
    return NextResponse.json(
      { detail: "Backend not configured" },
      { status: 500 }
    );
  }
  const url = `${BASE}/api/workflows${path}`;
  try {
    const res = await fetch(url, {
      method: options.method,
      headers: buildHeaders(request),
      body: options.body,
      cache: "no-store",
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      return NextResponse.json(data?.detail ?? data, { status: res.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 503 }
    );
  }
}

export async function proxyRagToBackend(
  request: NextRequest,
  path: string,
  options: { method: "GET" | "POST" | "PATCH"; body?: string } = { method: "GET" }
): Promise<NextResponse> {
  if (!BASE) {
    return NextResponse.json(
      { detail: "Backend not configured" },
      { status: 500 }
    );
  }
  const url = `${BASE}/api/rag${path}`;
  try {
    const res = await fetch(url, {
      method: options.method,
      headers: buildHeaders(request),
      body: options.body,
      cache: "no-store",
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      return NextResponse.json(data?.detail ?? data, { status: res.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 503 }
    );
  }
}

export async function proxyOrgToBackend(
  request: NextRequest,
  path: string,
  options: { method: "GET" | "POST" | "PATCH" | "DELETE"; body?: string } = { method: "GET" }
): Promise<NextResponse> {
  if (!BASE) {
    return NextResponse.json(
      { detail: "Backend not configured" },
      { status: 500 }
    );
  }
  const url = `${BASE}/api/org${path}`;
  try {
    const res = await fetch(url, {
      method: options.method,
      headers: buildHeaders(request),
      body: options.body,
      cache: "no-store",
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      return NextResponse.json(data?.detail ?? data, { status: res.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 503 }
    );
  }
}

export async function proxyMetricsToBackend(
  request: NextRequest,
  path: string,
  options: { method: "GET" } = { method: "GET" }
): Promise<NextResponse> {
  if (!BASE) {
    return NextResponse.json(
      { detail: "Backend not configured" },
      { status: 500 }
    );
  }
  const url = `${BASE}/api/metrics${path}`;
  try {
    const res = await fetch(url, {
      method: options.method,
      headers: buildHeaders(request),
      cache: "no-store",
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      return NextResponse.json(data?.detail ?? data, { status: res.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 503 }
    );
  }
}

export async function proxyApiToBackend(
  request: NextRequest,
  apiPath: string,
  options: { method: "GET" | "POST" | "PATCH" | "DELETE"; body?: string } = { method: "GET" }
): Promise<NextResponse> {
  if (!BASE) {
    return NextResponse.json(
      { detail: "Backend not configured" },
      { status: 500 }
    );
  }
  const url = `${BASE}${apiPath.startsWith("/") ? apiPath : `/${apiPath}`}`;
  try {
    const res = await fetch(url, {
      method: options.method,
      headers: buildHeaders(request),
      body: options.body,
      cache: "no-store",
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      return NextResponse.json(data?.detail ?? data, { status: res.status });
    }
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 503 }
    );
  }
}
