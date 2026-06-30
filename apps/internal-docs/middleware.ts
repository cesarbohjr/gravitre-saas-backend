import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

export function middleware(request: NextRequest) {
  const password = process.env.INTERNAL_DOCS_PASSWORD?.trim()
  if (!password) {
    return new NextResponse("Internal docs password not configured", { status: 503 })
  }

  const auth = request.headers.get("authorization")
  if (auth) {
    const [scheme, encoded] = auth.split(" ")
    if (scheme?.toLowerCase() === "basic" && encoded) {
      const decoded = atob(encoded)
      const [, supplied] = decoded.split(":")
      if (supplied === password) {
        return NextResponse.next()
      }
    }
  }

  return new NextResponse("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Gravitre Internal Docs"' },
  })
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
}
