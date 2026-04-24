"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/lib/use-auth";
import { getEnvironmentHeader } from "@/lib/environment";

type NavItem = { label: string; href: string };
type NavGroup = { label: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Operate",
    items: [
      { label: "AI Operator", href: "/operator" },
      { label: "Agents", href: "/agents" },
    ],
  },
  {
    label: "Build",
    items: [
      { label: "Workflows", href: "/workflows" },
      { label: "Integrations", href: "/integrations" },
      { label: "Sources", href: "/sources" },
    ],
  },
  {
    label: "Run",
    items: [
      { label: "Runs", href: "/runs" },
      { label: "Approvals", href: "/approvals" },
    ],
  },
  {
    label: "Observe",
    items: [
      { label: "Metrics", href: "/metrics" },
      { label: "Audit", href: "/audit" },
    ],
  },
  {
    label: "Billing",
    items: [
      { label: "Pricing", href: "/pricing" },
      { label: "Billing", href: "/billing" },
    ],
  },
  {
    label: "Admin",
    items: [
      { label: "Environments", href: "/environments" },
      { label: "Settings", href: "/settings" },
    ],
  },
];

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isNavOpen, setIsNavOpen] = useState(false);
  const auth = useAuth();
  const environment = getEnvironmentHeader();
  const isAdmin = auth.status === "authenticated" && auth.role === "admin";
  const orgLabel =
    auth.status === "authenticated" && auth.orgId
      ? `Org ${auth.orgId.slice(0, 8)}…`
      : "Org";

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border bg-background px-6 py-3">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-xs text-muted-foreground">Organization</div>
            <div className="rounded-md border border-border bg-muted/40 px-2 py-1 text-sm">
              {orgLabel}
            </div>
            <div className="flex items-center gap-2">
              <div className="text-xs text-muted-foreground">Environment (read-only)</div>
              <div className="rounded-md border border-border bg-muted/40 px-2 py-1 text-sm">
                {environment}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              className="lg:hidden"
              onClick={() => setIsNavOpen(true)}
            >
              Menu
            </Button>
            <div className="hidden items-center gap-2 lg:flex">
              <Button variant="secondary" size="sm" disabled title="Coming soon">
                Search / Cmd+K
              </Button>
            </div>
            <Button
              variant="primary"
              size="sm"
              disabled={!isAdmin}
              title={!isAdmin ? "Admin only" : undefined}
            >
              + Create
            </Button>
            <div className="hidden items-center gap-2 lg:flex">
              <Button variant="secondary" size="sm" disabled title="Coming soon">
                Notifications
              </Button>
              <span className="text-xs text-muted-foreground">Coming soon</span>
            </div>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <div className="rounded-md border border-border bg-muted/40 px-2 py-1 text-sm">
                {auth.status === "authenticated" ? auth.role ?? "member" : "User"}
              </div>
            </div>
          </div>
        </div>
      </header>

      {isNavOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/40 lg:hidden"
          onClick={() => setIsNavOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="h-full w-72 bg-[hsl(var(--surface))] border-r border-border px-4 py-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <span className="text-lg font-semibold tracking-tight text-foreground">
                Gravitre
              </span>
              <Button variant="secondary" size="sm" onClick={() => setIsNavOpen(false)}>
                Close
              </Button>
            </div>
            <nav className="space-y-6" aria-label="Product navigation">
              {NAV_GROUPS.map((group) => (
                <div key={group.label}>
                  <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                    {group.label}
                  </div>
                  <ul className="mt-2 space-y-1">
                    {group.items.map((item) => {
                      const active = isActivePath(pathname, item.href);
                      return (
                        <li key={item.href}>
                          <Link
                            href={item.href}
                            aria-current={active ? "page" : undefined}
                            onClick={() => setIsNavOpen(false)}
                            className={`flex items-center rounded-md px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                              active
                                ? "bg-muted text-foreground"
                                : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                            }`}
                          >
                            {item.label}
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </nav>
          </div>
        </div>
      )}

      <div className="flex min-h-[calc(100vh-60px)]">
        <aside className="hidden w-64 flex-shrink-0 border-r border-border bg-[hsl(var(--surface))] px-4 py-6 lg:block">
          <div className="mb-6">
            <Link
              href="/"
              className="text-lg font-semibold tracking-tight text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
            >
              Gravitre
            </Link>
          </div>
          <nav className="space-y-6" aria-label="Product navigation">
            {NAV_GROUPS.map((group) => (
              <div key={group.label}>
                <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  {group.label}
                </div>
                <ul className="mt-2 space-y-1">
                  {group.items.map((item) => {
                    const active = isActivePath(pathname, item.href);
                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          aria-current={active ? "page" : undefined}
                          className={`flex items-center rounded-md px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                            active
                              ? "bg-muted text-foreground"
                              : "text-muted-foreground hover:text-foreground hover:bg-muted/60"
                          }`}
                        >
                          {item.label}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        <main className="flex-1 px-6 py-6">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
