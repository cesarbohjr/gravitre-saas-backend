"use client"

import Link from "next/link"
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
  { title: "Docs", href: "/docs" },
]

const company = [
  { title: "Log in", href: "/login" },
  { title: "About", href: "/about" },
  { title: "Contact", href: "/contact" },
  { title: "Careers", href: "/careers" },
  { title: "Blog", href: "/blog" },
  { title: "Changelog", href: "/changelog" },
]

const legal = [
  { title: "Privacy", href: "/privacy" },
  { title: "Terms", href: "/terms" },
  { title: "Security", href: "/security" },
]

export const Footer = () => {
  return (
    <Container>
      <div className="grid grid-cols-1 px-4 py-20 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-6">
        <div className="mb-6 sm:col-span-2 md:col-span-4 lg:col-span-2">
          <Logo />
          <SubHeading as="p" className="mt-4 max-w-lg text-left">
            One AI brain for your entire business.
          </SubHeading>
          <Button as={Link} href="/get-started" className="mt-4 mb-8 lg:mb-0">
            Put Gravitre to work
          </Button>
        </div>
        <div className="col-span-1 mb-4 flex flex-col gap-2 md:mb-0">
          <p className="text-sm font-medium text-gray-600">Product</p>
          {product.map((item) => (
            <Link href={item.href} key={item.title} className="text-footer-link my-2 text-sm font-medium">
              {item.title}
            </Link>
          ))}
        </div>
        <div className="col-span-1 mb-4 flex flex-col gap-2 md:mb-0">
          <p className="text-sm font-medium text-gray-600">Company</p>
          {company.map((item) => (
            <Link href={item.href} key={item.title} className="text-footer-link my-2 text-sm font-medium">
              {item.title}
            </Link>
          ))}
        </div>
        <div className="col-span-1 mb-4 flex flex-col gap-2 md:mb-0 lg:col-span-2">
          <p className="text-sm font-medium text-gray-600">Legal</p>
          {legal.map((item) => (
            <Link href={item.href} key={item.title} className="text-footer-link my-2 text-sm font-medium">
              {item.title}
            </Link>
          ))}
          <button
            type="button"
            onClick={() => openMarketingConsentSettings()}
            className="text-footer-link my-2 text-left text-sm font-medium"
          >
            Cookie settings
          </button>
        </div>
      </div>
      <div className="my-4 flex flex-col items-center justify-between px-4 pt-8 md:flex-row">
        <p className="text-footer-link text-sm">© {new Date().getFullYear()} Gravitre. All rights reserved.</p>
      </div>
    </Container>
  )
}
