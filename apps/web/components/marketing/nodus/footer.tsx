"use client"

import Link from "next/link"
import { Linkedin, Instagram, AtSign } from "lucide-react"
import { GRAVITRE_SOCIAL_PROFILES } from "@/lib/company-social-profiles"
import { Button } from "./button"
import { Container } from "./container"
import { Logo } from "./logo"
import { SubHeading } from "./subheading"
import { openMarketingConsentSettings } from "@/lib/marketing-consent"

const product = [
  { title: "Features", href: "/features" },
  { title: "Technology", href: "/features/technology" },
  { title: "Extension", href: "/features/extension" },
  { title: "Download", href: "/download" },
  { title: "Pricing", href: "/pricing" },
  { title: "Marketplace", href: "/features/marketplace" },
]

const enterprise = [
  { title: "Security", href: "/security" },
  { title: "Docs", href: "/docs" },
  { title: "API", href: "/api" },
  { title: "Support", href: "/support" },
]

const resources = [
  { title: "Guides", href: "/guides" },
  { title: "Blog", href: "/blog" },
  { title: "Changelog", href: "/changelog" },
  { title: "Roadmap", href: "/roadmap" },
  { title: "Contact", href: "/contact" },
]

const company = [
  { title: "About", href: "/about" },
  { title: "Careers", href: "/careers" },
  { title: "Log in", href: "/login" },
  { title: "Get started", href: "/get-started" },
]

const legal = [
  { title: "Privacy", href: "/privacy" },
  { title: "Terms", href: "/terms" },
]

function FooterColumn({
  title,
  items,
  className = "",
}: {
  title: string
  items: Array<{ title: string; href: string }>
  className?: string
}) {
  return (
    <div className={`col-span-1 mb-6 flex flex-col gap-1 md:mb-0 ${className}`}>
      <p className="mb-2 text-sm font-medium text-gray-600">{title}</p>
      {items.map((item) => (
        <Link
          href={item.href}
          key={item.title}
          className="text-footer-link my-1.5 text-sm font-medium transition-colors hover:text-charcoal-700"
        >
          {item.title}
        </Link>
      ))}
    </div>
  )
}

function SocialProfiles() {
  return (
    <nav className="flex flex-wrap items-center gap-3" aria-label="Gravitre social media">
      {GRAVITRE_SOCIAL_PROFILES.map((profile) => (
        <a
          key={profile.name}
          href={profile.url}
          target="_blank"
          rel="noopener noreferrer me"
          aria-label={`Gravitre on ${profile.name}`}
          title={`Gravitre on ${profile.name}`}
          className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-divide text-charcoal-700 transition-colors hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-charcoal-700"
        >
          {profile.name === "LinkedIn" ? <Linkedin aria-hidden="true" size={18} /> :
           profile.name === "Instagram" ? <Instagram aria-hidden="true" size={18} /> :
           profile.name === "Threads" ? <AtSign aria-hidden="true" size={18} /> :
           <span aria-hidden="true" className="text-base font-semibold">𝕏</span>}
        </a>
      ))}
    </nav>
  )
}

function SlimFooter() {
  return (
    <footer
      className="relative isolate overflow-hidden border-t border-divide bg-[color:var(--g-marketing-canvas)]"
      data-marketing-footer="slim"
    >
      <Container className="relative">
        <div className="flex flex-col items-center justify-between gap-4 px-4 py-8 md:flex-row">
          <div className="flex flex-col items-center gap-3 md:items-start"><Logo /><SocialProfiles /></div>
          <nav className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2" aria-label="Legal">
            {legal.map((item) => (
              <Link
                key={item.title}
                href={item.href}
                className="text-footer-link text-sm font-medium transition-colors hover:text-charcoal-700"
              >
                {item.title}
              </Link>
            ))}
            <button
              type="button"
              onClick={() => openMarketingConsentSettings()}
              className="text-footer-link text-sm font-medium transition-colors hover:text-charcoal-700"
            >
              Cookie settings
            </button>
          </nav>
          <p className="text-footer-link text-sm">
            © {new Date().getFullYear()} Gravitre
          </p>
        </div>
      </Container>
    </footer>
  )
}

/**
 * Marketing System 4.0 footer — full site columns + TRACE, or slim auth legal bar.
 */
export function Footer({ variant = "full" }: { variant?: "full" | "slim" }) {
  if (variant === "slim") {
    return <SlimFooter />
  }

  return (
    <footer className="relative isolate overflow-hidden bg-[color:var(--g-marketing-canvas)]" data-marketing-footer="full">
      <Container className="relative">
        <div className="grid grid-cols-1 gap-y-2 px-4 pt-16 pb-10 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-8 lg:gap-x-4 lg:pt-20">
          <div className="mb-8 sm:col-span-2 md:col-span-4 lg:col-span-2 lg:mb-0">
            <Logo />
            <SubHeading as="p" className="mt-4 max-w-sm text-left">
              One AI brain for your entire business.
            </SubHeading>
            <div className="mt-4"><SocialProfiles /></div>
            <Button as={Link} href="/get-started" className="mt-5">
              Put Gravitre to work
            </Button>
          </div>

          <FooterColumn title="Product" items={product} />
          <FooterColumn title="Enterprise" items={enterprise} />
          <FooterColumn title="Resources" items={resources} />
          <FooterColumn title="Company" items={company} />
          <div className="col-span-1 mb-6 flex flex-col gap-1 md:mb-0 lg:col-span-1">
            <p className="mb-2 text-sm font-medium text-gray-600">Legal</p>
            {legal.map((item) => (
              <Link
                href={item.href}
                key={item.title}
                className="text-footer-link my-1.5 text-sm font-medium transition-colors hover:text-charcoal-700"
              >
                {item.title}
              </Link>
            ))}
            <button
              type="button"
              onClick={() => openMarketingConsentSettings()}
              className="text-footer-link my-1.5 text-left text-sm font-medium transition-colors hover:text-charcoal-700"
            >
              Cookie settings
            </button>
          </div>
        </div>

        <div className="mx-4 border-t border-divide" />
        <div className="flex flex-col items-center justify-between gap-3 px-4 py-6 md:flex-row">
          <p className="text-footer-link text-sm">
            © {new Date().getFullYear()} Gravitre. All rights reserved.
          </p>
          <p className="text-footer-link text-xs tracking-wide uppercase">
            Connect · Understand · Coordinate · Act · Verify · Learn
          </p>
        </div>
      </Container>
    </footer>
  )
}
