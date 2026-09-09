"use client"

import { useState } from "react"
import Link from "next/link"
import { Badge } from "@/components/marketing/nodus/badge"
import { Button } from "@/components/marketing/nodus/button"
import { Container } from "@/components/marketing/nodus/container"
import { DivideX } from "@/components/marketing/nodus/divide"
import { Heading } from "@/components/marketing/nodus/heading"
import { LogoSVG } from "@/components/marketing/nodus/logo"
import { SubHeading } from "@/components/marketing/nodus/subheading"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  GravitreAmbientMotion,
  GravitreResolve,
  SignalFieldVisual,
} from "@/components/marketing/system"

const contactOptions = [
  {
    title: "Support",
    description: "Help with your account or technical issues",
    action: "support@gravitre.app",
    href: "mailto:support@gravitre.app",
  },
  {
    title: "Sales",
    description: "Enterprise plans and custom solutions",
    action: "sales@gravitre.app",
    href: "mailto:sales@gravitre.app",
  },
  {
    title: "Partnerships",
    description: "Integrations and partnership opportunities",
    action: "partners@gravitre.app",
    href: "mailto:partners@gravitre.app",
  },
]

/**
 * Contact — Nodus form layout · Gravitre routing · Marketing System 4.0 signal field.
 * Form posts via mailto fallback until a live handler is wired.
 */
export default function ContactPage() {
  const [formState, setFormState] = useState({
    name: "",
    email: "",
    message: "",
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSubmitted, setIsSubmitted] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSubmitting(true)
    const subject = encodeURIComponent(`Gravitre contact from ${formState.name || "visitor"}`)
    const body = encodeURIComponent(
      `Name: ${formState.name}\nEmail: ${formState.email}\n\n${formState.message}`,
    )
    window.location.href = `mailto:support@gravitre.app?subject=${subject}&body=${body}`
    setIsSubmitting(false)
    setIsSubmitted(true)
  }

  return (
    <main className="bg-[color:var(--g-marketing-canvas)]">
      <Container className="border-divide min-h-[calc(100vh-8rem)] border-x py-10 md:py-20">
        <div className="grid grid-cols-1 gap-10 px-4 md:grid-cols-2 md:px-8 lg:gap-20">
          <div>
            <LogoSVG className="text-brand size-6" />
            <Badge text="Contact" />
            <Heading className="mt-4 text-left lg:text-4xl">Get in touch</Heading>
            <SubHeading as="p" className="mt-4 max-w-xl text-left">
              Questions about Gravitre? Send a message and we will respond as soon as we can.
            </SubHeading>

            {isSubmitted ? (
              <GravitreResolve className="mt-8 rounded-2xl border border-divide bg-gray-50 p-6">
                <p className="text-charcoal-700 font-medium">Thanks — your mail client should open next.</p>
                <p className="mt-2 text-sm text-gray-600">
                  If it did not, email{" "}
                  <a className="text-brand underline-offset-4 hover:underline" href="mailto:support@gravitre.app">
                    support@gravitre.app
                  </a>
                  .
                </p>
              </GravitreResolve>
            ) : (
              <form className="mt-6 flex flex-col gap-6" onSubmit={handleSubmit}>
                <div>
                  <Label htmlFor="name">Name</Label>
                  <Input
                    id="name"
                    type="text"
                    required
                    className="mt-2"
                    placeholder="Your name"
                    value={formState.name}
                    onChange={(e) => setFormState((s) => ({ ...s, name: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    required
                    className="mt-2"
                    placeholder="you@company.com"
                    value={formState.email}
                    onChange={(e) => setFormState((s) => ({ ...s, email: e.target.value }))}
                  />
                </div>
                <div>
                  <Label htmlFor="message">Message</Label>
                  <Textarea
                    id="message"
                    required
                    className="mt-2 min-h-40"
                    placeholder="How can we help?"
                    value={formState.message}
                    onChange={(e) => setFormState((s) => ({ ...s, message: e.target.value }))}
                  />
                </div>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Opening…" : "Send message"}
                </Button>
              </form>
            )}
          </div>

          <div className="flex flex-col gap-4">
            <GravitreAmbientMotion className="mb-2 flex justify-center md:justify-end">
              <SignalFieldVisual />
            </GravitreAmbientMotion>
            <p className="font-mono text-xs tracking-tight text-neutral-500 uppercase">
              Direct lines
            </p>
            {contactOptions.map((option) => (
              <a
                key={option.title}
                href={option.href}
                className="rounded-2xl border border-divide bg-gray-50 p-5 transition hover:bg-gray-100"
              >
                <h3 className="text-charcoal-700 text-lg font-medium">{option.title}</h3>
                <p className="mt-1 text-sm text-gray-600">{option.description}</p>
                <p className="text-brand mt-3 text-sm font-medium">{option.action}</p>
              </a>
            ))}
            <Button as={Link} href="/docs" variant="secondary" className="mt-2 w-full">
              Read docs
            </Button>
          </div>
        </div>
      </Container>
      <DivideX />
    </main>
  )
}
