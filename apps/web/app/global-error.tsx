"use client"

import { useEffect } from "react"

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("Global error:", error)
  }, [error])

  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen items-center justify-center p-4">
          <div className="max-w-md space-y-4 text-center">
            <h1 className="text-2xl font-semibold">Something went wrong</h1>
            <p className="text-sm text-neutral-600">
              {error.digest
                ? `Error ID: ${error.digest}`
                : "An unexpected error occurred."}
            </p>
            <button
              type="button"
              onClick={reset}
              className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white"
            >
              Try again
            </button>
          </div>
        </div>
      </body>
    </html>
  )
}
