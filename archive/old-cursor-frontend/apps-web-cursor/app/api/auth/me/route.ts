import { NextRequest, NextResponse } from "next/server";

/**
 * FE-00: Single-origin proxy for GET /api/auth/me.
 * Forwards request to FastAPI; backend URL from server-only FASTAPI_BASE_URL.
 * Browser never calls FastAPI directly — no CORS.
 */
export async function GET(request: NextRequest) {
  const baseUrl = process.env.FASTAPI_BASE_URL;
  if (!baseUrl) {
    return NextResponse.json(
      { detail: "Backend not configured" },
      { status: 502 }
    );
  }

  const authHeader = request.headers.get("authorization") ?? "";
  const url = `${baseUrl.replace(/\/$/, "")}/api/auth/me`;

  try {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: authHeader,
        "Content-Type": "application/json",
      },
      cache: "no-store",
    });

    const body = await res.text();
    const data = body ? JSON.parse(body) : {};

    if (res.status === 401) {
      return NextResponse.json(data, { status: 401 });
    }

    if (!res.ok) {
      return NextResponse.json(
        data?.detail ?? { detail: "Backend error" },
        { status: res.status }
      );
    }

    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { detail: "Backend unavailable" },
      { status: 502 }
    );
  }
}
