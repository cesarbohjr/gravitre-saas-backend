import { PersistentAppShell } from "@/components/gravitre/app-shell"

/**
 * Signed-in product routes share one shell.
 *
 * Every route in this group used to wrap itself in `<AppShell>`, so the
 * sidebar, top bar, banners and their fetches (billing status, /auth/me,
 * onboarding, nav counts) unmounted and remounted on every navigation. The
 * group's layout persists across client navigation between any of these
 * routes, so the chrome is mounted once here. Pages keep declaring their
 * title / full-viewport mode with `<AppShell …>`, which under this layout only
 * registers options (see components/gravitre/app-shell-context.tsx).
 *
 * The `(app)` folder is a route group: it does not appear in URLs. Marketing,
 * auth, onboarding/welcome and other public routes live outside it and stay
 * shell-free.
 */
export default function SignedInAppLayout({ children }: { children: React.ReactNode }) {
  return <PersistentAppShell>{children}</PersistentAppShell>
}
