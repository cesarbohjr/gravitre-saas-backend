"use client"

import { useEffect } from "react"
import Link from "next/link"
import { ErrorState } from "@/components/gravitre/empty-state"
import { Button } from "@/components/ui/button"
import { APP_ROUTES } from "@/lib/app-routes"

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error("[Gravitre] route error:", error)
  }, [error])

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center p-6">
      <ErrorState
        title="Something went wrong"
        description={
          error.message ||
          "This page hit an unexpected error. You can retry or return to your home dashboard."
        }
        onRetry={reset}
      />
      {error.digest ? (
        <p className="mt-4 font-mono text-xs text-muted-foreground">Error ID: {error.digest}</p>
      ) : null}
      <Button variant="outline" asChild className="mt-4">
        <Link href={APP_ROUTES.home}>Go to home</Link>
      </Button>
    </div>
  )
}
