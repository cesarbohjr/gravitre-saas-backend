"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { ArrowRight, Menu, X, ChevronDown } from "lucide-react"
import { openMarketingConsentSettings } from "@/lib/marketing-consent"

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

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20)
    }
    window.addEventListener("scroll", handleScroll)
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  // Keep <html> in dark so CSS variables / void stay graphite even if a parent
  // theme provider toggles light on the document root.
  useEffect(() => {
    const root = document.documentElement
    const hadDark = root.classList.contains("dark")
    root.classList.add("dark")
    root.dataset.marketingCanvas = "graphite"
    return () => {
      if (!hadDark) root.classList.remove("dark")
      delete root.dataset.marketingCanvas
    }
  }, [])

  // Auto-close menus whenever the route changes (covers both link taps and
  // programmatic navigation), so the overlay never lingers over the page.
  useEffect(() => {
    setMobileMenuOpen(false)
    setCompanyDropdownOpen(false)
    setFeaturesDropdownOpen(false)
  }, [pathname])

  // Lock background scroll while the mobile menu overlay is open.
  useEffect(() => {
    if (!mobileMenuOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    return () => {
      document.body.style.overflow = previous
    }
  }, [mobileMenuOpen])

  return (
    <div className="dark min-h-screen bg-background text-foreground" data-marketing-canvas="graphite">
      {/* Navigation */}
      <header 
        className={`fixed top-0 left-0 right-0 z-[100] transition-all duration-300 ${
          scrolled 
            ? "border-b border-border bg-background/95 backdrop-blur-xl shadow-sm" 
            : "bg-background/95 backdrop-blur-sm"
        }`}
        style={{ position: 'fixed' }}
      >
        <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-8">
            {/* Logo */}
            <Link href="/" className="flex items-center group">
              <img
                src="/images/gravitre-logo-white.png"
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
                        if (link.label === "Features") {
                          setFeaturesDropdownOpen((open) => !open)
                          setCompanyDropdownOpen(false)
                        } else {
                          setCompanyDropdownOpen((open) => !open)
                          setFeaturesDropdownOpen(false)
                        }
                      }}
                      className={`flex items-center gap-1 rounded-full px-4 py-2 text-sm font-medium transition-all ${
                        (link.label === "Features" && featuresDropdownOpen) ||
                        (link.label === "Company" && companyDropdownOpen)
                          ? "text-foreground bg-muted"
                          : link.label === "Features" && pathname.startsWith("/features")
                            ? "text-foreground bg-muted"
                            : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                      }`}
                    >
                      {link.label}
                      <ChevronDown
                        className={`h-3 w-3 transition-transform ${
                          (link.label === "Features" && featuresDropdownOpen) ||
                          (link.label === "Company" && companyDropdownOpen)
                            ? "rotate-180"
                            : ""
                        }`}
                      />
                    </button>
                    <AnimatePresence>
                      {(link.label === "Features" ? featuresDropdownOpen : companyDropdownOpen) && (
                        <motion.div
                          initial={{ opacity: 0, y: 10, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 10, scale: 0.95 }}
                          transition={{ duration: 0.15 }}
                          className={`absolute top-full left-0 mt-2 rounded-xl border border-border bg-card p-2 shadow-xl ${
                            link.label === "Features" ? "w-56 max-h-[70vh] overflow-y-auto" : "w-48"
                          }`}
                        >
                          {link.children.map((child) => (
                            <Link
                              key={child.href}
                              href={child.href}
                              onClick={() => {
                                setFeaturesDropdownOpen(false)
                                setCompanyDropdownOpen(false)
                              }}
                              className={`block rounded-lg px-4 py-2.5 text-sm transition-colors ${
                                pathname === child.href
                                  ? "bg-primary/10 text-primary"
                                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                              }`}
                            >
                              {child.label}
                            </Link>
                          ))}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                ) : (
                  <Link
                    key={link.href}
                    href={link.href!}
                    className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${
                      pathname === link.href
                        ? "text-foreground bg-muted"
                        : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                    }`}
                  >
                    {link.label}
                  </Link>
                )
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/login?intent=login"
              className="hidden sm:inline-flex text-sm font-medium text-muted-foreground transition-colors hover:text-foreground px-4 py-2"
            >
              Log in
            </Link>
            <Link
              href="/get-started"
              className="group relative hidden sm:inline-flex items-center gap-2 overflow-hidden rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow-[var(--g-shadow-surface)] transition-all duration-[var(--g-duration-micro)] hover:opacity-95 hover:shadow-[var(--g-glow-operational)] active:scale-[0.98]"
            >
              <span className="absolute inset-0 bg-gradient-to-b from-white/12 to-transparent opacity-50" />
              <span className="relative">Get Started</span>
              <ArrowRight className="relative h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <button
              onClick={() => setMobileMenuOpen((open) => !open)}
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileMenuOpen}
              className="inline-flex h-11 w-11 items-center justify-center rounded-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors md:hidden"
            >
              {mobileMenuOpen ? (
                <X className="h-5 w-5" />
              ) : (
                <Menu className="h-5 w-5" />
              )}
            </button>
          </div>
        </nav>

        {/* Mobile Menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="border-t border-border bg-background md:hidden overflow-hidden"
            >
              <div className="px-4 py-4 space-y-1">
                {navLinks.map((link) => (
                  link.children ? (
                    <div key={link.label}>
                      <div className="px-4 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                        {link.label}
                      </div>
                      {link.children.map((child) => (
                        <Link
                          key={child.href}
                          href={child.href}
                          onClick={() => setMobileMenuOpen(false)}
                          className="block rounded-xl px-4 py-3 text-base text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
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
                          ? "bg-muted text-foreground font-medium"
                          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                      }`}
                    >
                      {link.label}
                    </Link>
                  )
                ))}
                <div className="mt-4 flex flex-col gap-3 border-t border-border pt-4">
                  <Link
                    href="/login?intent=login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block rounded-xl px-4 py-3 text-center text-base text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
                  >
                    Log in
                  </Link>
                  <Link
                    href="/get-started"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center justify-center gap-2 rounded-full bg-primary px-6 py-3 text-base font-medium text-primary-foreground"
                  >
                    Get Started
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* Click outside handler for dropdown */}
      {(companyDropdownOpen || featuresDropdownOpen) && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={() => {
            setCompanyDropdownOpen(false)
            setFeaturesDropdownOpen(false)
          }}
        />
      )}

      {/* Main Content */}
      <main className="pt-16">
        {children}
      </main>

      {/* Footer - Light theme */}
      <footer className="relative border-t border-border bg-muted/50">
        {/* Gradient accent */}
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
        
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:py-20">
          <div className="grid grid-cols-2 gap-6 sm:gap-8 md:grid-cols-5">
            <div className="col-span-2 md:col-span-1">
              {/* Footer Logo */}
              <Link href="/" className="flex items-center">
                <img
                  src="/images/gravitre-logo-white.png"
                  alt="Gravitre"
                  className="h-8 w-auto opacity-90"
                />
              </Link>
              <p className="mt-4 text-sm text-muted-foreground leading-relaxed">
                Your AI team, managed simply.
              </p>
              <div className="mt-6 flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-primary" />
                <span className="text-xs text-primary font-medium">Product documentation</span>
              </div>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground">Product</h4>
              <ul className="mt-4 space-y-3">
                {[
                  { href: "/features", label: "Features" },
                  { href: "/features/extension", label: "Browser extension" },
                  { href: "/pricing", label: "Pricing" },
                  { href: "/changelog", label: "Changelog" },
                  { href: "/roadmap", label: "Roadmap" },
                ].map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground">Company</h4>
              <ul className="mt-4 space-y-3">
                {[
                  { href: "/about", label: "About" },
                  { href: "/blog", label: "Blog" },
                  { href: "/careers", label: "Careers" },
                  { href: "/contact", label: "Contact" },
                ].map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground">Help</h4>
              <ul className="mt-4 space-y-3">
                {[
                  { href: "/docs", label: "Docs" },
                  { href: "/api", label: "API" },
                  { href: "/guides", label: "Guides" },
                  { href: "/support", label: "Support" },
                ].map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-foreground">Legal</h4>
              <ul className="mt-4 space-y-3">
                {[
                  { href: "/privacy", label: "Privacy" },
                  { href: "/terms", label: "Terms" },
                  { href: "/security", label: "Security" },
                ].map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                      {link.label}
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
          
          <div className="mt-16 flex flex-col items-center justify-between gap-6 border-t border-border pt-8 md:flex-row">
            <p className="text-sm text-muted-foreground">
              &copy; {new Date().getFullYear()} Gravitre. All rights reserved.
            </p>
            <div className="flex items-center gap-6">
              <Link href="https://twitter.com" className="text-muted-foreground hover:text-foreground transition-colors">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
              </Link>
              <Link href="https://github.com" className="text-muted-foreground hover:text-foreground transition-colors">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0012 2z"/></svg>
              </Link>
              <Link href="https://linkedin.com" className="text-muted-foreground hover:text-foreground transition-colors">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
