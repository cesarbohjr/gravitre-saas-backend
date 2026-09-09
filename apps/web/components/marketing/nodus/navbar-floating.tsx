"use client"

import Link from "next/link"
import { motion, useScroll, useSpring, useTransform } from "framer-motion"
import { Logo } from "./logo"
import { Button } from "./button"

export function FloatingNav({ items }: { items: ReadonlyArray<{ title: string; href: string }> }) {
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
