"use client";

import Link from "next/link";
import { ThemeToggle } from "@/components/theme-toggle";

/**
 * FE-10: Shared header with nav. Brand Spec: calm, token-based.
 */
export function AppHeader() {
  return (
    <header
      className="border-b border-border bg-background px-6 py-4"
      role="banner"
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between">
        <nav className="flex items-center gap-6" aria-label="Main">
          <Link
            href="/"
            className="text-xl font-semibold tracking-tight text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-sm"
          >
            Gravitre
          </Link>
          <Link
            href="/workflows"
            className="text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-sm"
          >
            Workflows
          </Link>
          <Link
            href="/rag/sources"
            className="text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-sm"
          >
            Sources
          </Link>
          <Link
            href="/metrics"
            className="text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 rounded-sm"
          >
            Metrics
          </Link>
        </nav>
        <ThemeToggle />
      </div>
    </header>
  );
}
