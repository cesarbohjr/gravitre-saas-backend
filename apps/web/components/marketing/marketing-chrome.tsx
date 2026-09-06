"use client"

import { useState, useEffect, useRef } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTheme } from "next-themes"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowRight, Menu, X, ChevronDown } from "lucide-react"
import { openMarketingConsentSettings } from "@/lib/marketing-consent"
import { MARKETING_COPY } from "@/lib/marketing-copy"

const navLinks = [
  { href: "/features", label: "Features" },
  { href: "/features/technology", label: "Technology" },
  { href: "/features/marketplace", label: "Marketplace" },
  { href: "/features/extension", label: "Extension" },
  { href: "/download", label: "Download" },
  { href: "/pricing", label: "Pricing" },
  { href: "/docs", label: "Docs" },
  {
    label: "Company",
    children: [
      { href: "/about", label: "About" },
      { href: "/blog", label: "Blog" },
      { href: "/careers", label: "Careers" },
      { href: "/contact", label: "Contact" },
    ],
  },
]

export function MarketingChrome({
  children,
}: {
  children: React.ReactNode
}) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [companyDropdownOpen, setCompanyDropdownOpen] = useState(false)
  const [featuresDropdownOpen, setFeaturesDropdownOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const pathname = usePathname()
  const { setTheme } = useTheme()
  const savedThemeRef = useRef<string | null>(null)

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20)
    }
    window.addEventListener("scroll", handleScroll)
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  // UI 3.0 Phase 3: light-first marketing daylight canvas.
  // Restore the user's ThemeProvider preference on leave so the product app
  // keeps working light / dark / system.
  useEffect(() => {
    const root = document.documentElement
    savedThemeRef.current = localStorage.getItem("theme")
    root.dataset.marketingCanvas = "daylight"
    setTheme("light")
    return () => {
      delete root.dataset.marketingCanvas
      setTheme(savedThemeRef.current || "system")
    }
  }, [setTheme])

  useEffect(() => {
    setMobileMenuOpen(false)
    setCompanyDropdownOpen(false)
    setFeaturesDropdownOpen(false)
  }, [pathname])

  useEffect(() => {
    if (!mobileMenuOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = previous
    }
  }, [mobileMenuOpen])

  return (
    <div className="min-h-screen bg-background text-foreground" data-marketing-canvas="daylight">
      <header
        className={`fixed top-0 left-0 right-0 z-[100] transition-all duration-300 ${
          scrolled
            ? "border-b border-border bg-background/90 backdrop-blur-xl shadow-[var(--g-shadow-surface)]"
            : "bg-background/70 backdrop-blur-md"
        }`}
        style={{ position: "fixed" }}
      >
        <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-8">
            <Link href="/" className="flex items-center group">
              <img
                src="/images/gravitre-logo-black.png"
                alt="Gravitre"
                className="h-10 w-auto opacity-95 transition-opacity group-hover:opacity-100"
              />
            </Link>
            <div className="hidden md:flex items-center gap-1">
              {navLinks.map((link) =>
                link.children ? (
                  <div key={link.label} className="relative">
                    <button
                      onClick={() => {
                        setCompanyDropdownOpen((o) => !o)
                        setFeaturesDropdownOpen(false)
                      }}
                      className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
                    >
                      {link.label}
                      <ChevronDown className="h-3.5 w-3.5" />
                    </button>
                    <AnimatePresence>
                      {companyDropdownOpen ? (
                        <motion.div
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: 6 }}
                          className="absolute left-0 top-full z-50 mt-1 min-w-[11rem] rounded-xl border border-border bg-card p-1.5 shadow-[var(--g-shadow-elevated)]"
                        >
                          {link.children.map((child) => (
                            <Link
                              key={child.href}
                              href={child.href}
                              onClick={() => setCompanyDropdownOpen(false)}
                              className="block rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                            >
                              {child.label}
                            </Link>
                          ))}
                        </motion.div>
                      ) : null}
                    </AnimatePresence>
                  </div>
                ) : (
                  <Link
                    key={link.href}
                    href={link.href!}
                    className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                      pathname === link.href
                        ? "text-foreground bg-muted"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                    }`}
                  >
                    {link.label}
                  </Link>
                ),
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login?intent=login"
              className="hidden sm:inline-flex px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              Log in
            </Link>
            <Link
              href="/get-started"
              className="group relative hidden sm:inline-flex items-center gap-2 overflow-hidden rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-[var(--g-glow-operational)] transition-all duration-[var(--g-duration-micro)] hover:opacity-95 active:scale-[0.98]"
            >
              <span className="absolute inset-0 bg-gradient-to-b from-white/20 to-transparent opacity-60" />
              <span className="relative">Put Gravitre to work</span>
              <ArrowRight className="relative h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <button
              onClick={() => setMobileMenuOpen((open) => !open)}
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileMenuOpen}
              className="inline-flex h-11 w-11 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:hidden"
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </nav>

        <AnimatePresence>
          {mobileMenuOpen ? (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden border-t border-border bg-background md:hidden"
            >
              <div className="space-y-1 px-4 py-4">
                {navLinks.map((link) =>
                  link.children ? (
                    <div key={link.label}>
                      <div className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        {link.label}
                      </div>
                      {link.children.map((child) => (
                        <Link
                          key={child.href}
                          href={child.href}
                          onClick={() => setMobileMenuOpen(false)}
                          className="block rounded-xl px-4 py-3 text-base text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <Link
                      key={link.href}
                      href={link.href!}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`block rounded-xl px-4 py-3 text-base transition-colors ${
                        pathname === link.href
                          ? "bg-muted font-medium text-foreground"
                          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                      }`}
                    >
                      {link.label}
                    </Link>
                  ),
                )}
                <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4">
                  <Link
                    href="/login?intent=login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block rounded-xl px-4 py-3 text-center text-base text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
                  >
                    Log in
                  </Link>
                  <Link
                    href="/get-started"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-3 text-base font-semibold text-primary-foreground"
                  >
                    {MARKETING_COPY.hero.ctaPrimary}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </header>

      {(companyDropdownOpen || featuresDropdownOpen) && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => {
            setCompanyDropdownOpen(false)
            setFeaturesDropdownOpen(false)
          }}
        />
      )}

      <main className="pt-16">{children}</main>

      <footer className="relative border-t border-border bg-card/40">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:py-20">
          <div className="grid grid-cols-2 gap-6 sm:gap-8 md:grid-cols-5">
            <div className="col-span-2 md:col-span-1">
              <Link href="/" className="flex items-center">
                <img
                  src="/images/gravitre-logo-black.png"
                  alt="Gravitre"
                  className="h-8 w-auto opacity-90"
                />
              </Link>
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                One AI brain for your entire business.
              </p>
              <div className="mt-6 flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-primary" />
                <Link href="/docs" className="text-xs font-semibold text-primary hover:underline">
                  Product documentation
                </Link>
              </div>
            </div>
            {(
              [
                {
                  title: "Product",
                  items: [
                    { href: "/features", label: "Features" },
                    { href: "/features/extension", label: "Browser extension" },
                    { href: "/pricing", label: "Pricing" },
                    { href: "/changelog", label: "Changelog" },
                    { href: "/roadmap", label: "Roadmap" },
                  ],
                },
                {
                  title: "Company",
                  items: [
                    { href: "/about", label: "About" },
                    { href: "/blog", label: "Blog" },
                    { href: "/careers", label: "Careers" },
                    { href: "/contact", label: "Contact" },
                  ],
                },
                {
                  title: "Help",
                  items: [
                    { href: "/docs", label: "Docs" },
                    { href: "/docs/api/quickstart", label: "API" },
                    { href: "/docs/guides", label: "Guides" },
                    { href: "/contact", label: "Support" },
                  ],
                },
              ] as const
            ).map((col) => (
              <div key={col.title}>
                <h4 className="text-sm font-semibold text-foreground">{col.title}</h4>
                <ul className="mt-4 space-y-3">
                  {col.items.map((item) => (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {item.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            <div>
              <h4 className="text-sm font-semibold text-foreground">Legal</h4>
              <ul className="mt-4 space-y-3">
                {[
                  { href: "/privacy", label: "Privacy" },
                  { href: "/terms", label: "Terms" },
                  { href: "/security", label: "Security" },
                ].map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
                <li>
                  <button
                    type="button"
                    onClick={() => openMarketingConsentSettings()}
                    className="text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    Cookie settings
                  </button>
                </li>
              </ul>
            </div>
          </div>
          <div className="mt-12 flex flex-col gap-4 border-t border-border pt-8 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-muted-foreground">
              © {new Date().getFullYear()} Gravitre. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  )
}
