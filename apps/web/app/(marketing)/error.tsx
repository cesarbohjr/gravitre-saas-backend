"use client"

/**
 * Marketing segment error UI — recovers without inventing product claims.
 */
import Link from "next/link"
import { useEffect } from "react"
import { Button } from "@/components/marketing/nodus/button"

export default function MarketingError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      console.error("[marketing]", error)
    }
  }, [error])

  return (
    <div className="mx-auto flex min-h-[40vh] max-w-lg flex-col items-center justify-center gap-4 px-4 py-16 text-center">
      <h1 className="text-xl font-semibold text-foreground">Something went wrong</h1>
      <p className="text-sm text-muted-foreground">
        This page hit an unexpected error. You can try again or return home.
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button type="button" onClick={reset}>
          Try again
        </Button>
        <Button as={Link} href="/" variant="secondary">
          Home
        </Button>
      </div>
    </div>
  )
}
