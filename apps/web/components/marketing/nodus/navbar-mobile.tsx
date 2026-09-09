"use client"

import { useState } from "react"
import Link from "next/link"
import { AnimatePresence, motion } from "framer-motion"
import { CloseIcon, HamburgerIcon } from "@/components/marketing/nodus-icons/general"
import { Logo } from "./logo"
import { Button } from "./button"

export function MobileNav({ items }: { items: ReadonlyArray<{ title: string; href: string }> }) {
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
