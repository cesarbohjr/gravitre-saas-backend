"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { AlertCircle, Loader2 } from "lucide-react"

type LoadState = "loading" | "ready" | "unavailable"

export function SwaggerExplorer({ specUrl }: { specUrl: string }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<LoadState>("loading")

  useEffect(() => {
    let cancelled = false

    async function init() {
      try {
        // Preflight: confirm the spec is actually available before booting the
        // (heavy) Swagger bundle, so we can show a branded fallback instead of
        // Swagger UI's raw error screen when the backend spec is down.
        const probe = await fetch(specUrl, { method: "GET" })
        if (!probe.ok) {
          if (!cancelled) setState("unavailable")
          return
        }

        const [{ default: SwaggerUIBundle }] = await Promise.all([
          import("swagger-ui-dist/swagger-ui-es-bundle.js"),
          import("swagger-ui-dist/swagger-ui.css"),
        ])

        if (cancelled || !containerRef.current) return

        SwaggerUIBundle({
          domNode: containerRef.current,
          url: specUrl,
          deepLinking: true,
          docExpansion: "list",
          defaultModelsExpandDepth: 0,
          tryItOutEnabled: true,
          persistAuthorization: true,
          syntaxHighlight: { theme: "obsidian" },
        })
        if (!cancelled) setState("ready")
      } catch {
        if (!cancelled) setState("unavailable")
      }
    }

    void init()
    return () => {
      cancelled = true
    }
  }, [specUrl])

  return (
    <div>
      {state === "loading" && (
        <div className="flex items-center justify-center gap-2 py-20 text-sm text-zinc-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading API explorer…
        </div>
      )}

      {state === "unavailable" && (
        <div className="mx-auto my-12 max-w-md rounded-xl border border-amber-200 bg-amber-50 p-6 text-center">
          <AlertCircle className="mx-auto h-6 w-6 text-amber-600" />
          <h2 className="mt-3 font-medium text-zinc-900">API explorer temporarily unavailable</h2>
          <p className="mt-1 text-sm text-zinc-600">
            The live OpenAPI specification could not be loaded right now. You can still view the{" "}
            <a className="font-medium text-emerald-700 hover:underline" href={specUrl}>
              raw spec
            </a>{" "}
            or read the{" "}
            <Link className="font-medium text-emerald-700 hover:underline" href="/docs/api/quickstart">
              API quickstart
            </Link>
            .
          </p>
        </div>
      )}

      {/* Swagger renders here; keep mounted so the bundle has a target. */}
      <div ref={containerRef} className={state === "ready" ? "gravitre-swagger" : "sr-only"} />
    </div>
  )
}
