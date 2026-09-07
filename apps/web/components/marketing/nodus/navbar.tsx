"use client"

import React, { useState } from "react"
import { Logo } from "./logo"
import { Container } from "./container"
import Link from "next/link"
import { Button } from "./button"
import { CloseIcon, HamburgerIcon } from "@/components/marketing/nodus-icons/general"
import {
  AnimatePresence,
  motion,
  useScroll,
  useSpring,
  useTransform,
} from "framer-motion"

const items = [
  { title: "Pricing", href: "/pricing" },
  { title: "About", href: "/about" },
  { title: "Careers", href: "/careers" },
  { title: "Blog", href: "/blog" },
]

export const Navbar = () => {
  return (
    <Container as="nav" className="">
      <FloatingNav items={items} />
      <DesktopNav items={items} />
      <MobileNav items={items} />
    </Container>
  )
}

const MobileNav = ({ items }: { items: { title: string; href: string }[] }) => {
  const [isOpen, setIsOpen] = useState(false)
  return (
    <div className="relative flex items-center justify-between p-2 md:hidden">
      <Logo />
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="shadow-aceternity flex size-6 flex-col items-center justify-center rounded-md"
        aria-label="Toggle menu"
      >
        <HamburgerIcon className="size-4 shrink-0 text-gray-600" />
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-[60] h-full w-full bg-white shadow-lg"
          >
            <div className="flex items-center justify-between p-2">
              <Logo />
              <button
                onClick={() => setIsOpen(false)}
                className="shadow-aceternity flex size-6 flex-col items-center justify-center rounded-md"
                aria-label="Close menu"
              >
                <CloseIcon className="size-4 shrink-0 text-gray-600" />
              </button>
            </div>
            <div className="divide-divide border-divide mt-6 flex flex-col divide-y border-t">
              {items.map((item, index) => (
                <Link
                  href={item.href}
                  key={item.title}
                  className="px-4 py-2 font-medium text-gray-600 transition duration-200 hover:text-neutral-900"
                  onClick={() => setIsOpen(false)}
                >
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    transition={{ duration: 0.2, delay: index * 0.1 }}
                  >
                    {item.title}
                  </motion.div>
                </Link>
              ))}
              <div className="mt-4 space-y-2 p-4">
                <Button onClick={() => setIsOpen(false)} as={Link} href="/login" variant="secondary" className="w-full">
                  Log in
                </Button>
                <Button onClick={() => setIsOpen(false)} as={Link} href="/get-started" className="w-full">
                  Put Gravitre to work
                </Button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

const DesktopNav = ({ items }: { items: { title: string; href: string }[] }) => {
  return (
    <div className="hidden items-center justify-between px-4 py-4 md:flex">
      <Logo />
      <div className="flex items-center gap-10">
        {items.map((item) => (
          <Link
            className="font-medium text-gray-600 transition duration-200 hover:text-neutral-900"
            href={item.href}
            key={item.title}
          >
            {item.title}
          </Link>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Link href="/login" className="px-3 text-sm font-medium text-gray-600 hover:text-neutral-900">
          Log in
        </Link>
        <Button as={Link} href="/get-started">
          Put Gravitre to work
        </Button>
      </div>
    </div>
  )
}

const FloatingNav = ({ items }: { items: { title: string; href: string }[] }) => {
  const { scrollY } = useScroll()
  const springConfig = { stiffness: 300, damping: 30 }
  const y = useSpring(useTransform(scrollY, [100, 120], [-100, 10]), springConfig)
  return (
    <motion.div
      style={{ y }}
      className="shadow-aceternity fixed inset-x-0 top-0 z-50 mx-auto hidden max-w-[calc(80rem-4rem)] items-center justify-between bg-white/80 px-2 py-2 backdrop-blur-sm md:flex xl:rounded-2xl"
    >
      <Logo />
      <div className="flex items-center gap-10">
        {items.map((item) => (
          <Link
            className="font-medium text-gray-600 transition duration-200 hover:text-neutral-900"
            href={item.href}
            key={item.title}
          >
            {item.title}
          </Link>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Link href="/login" className="px-3 text-sm font-medium text-gray-600 hover:text-neutral-900">
          Log in
        </Link>
        <Button as={Link} href="/get-started">
          Put Gravitre to work
        </Button>
      </div>
    </motion.div>
  )
}
