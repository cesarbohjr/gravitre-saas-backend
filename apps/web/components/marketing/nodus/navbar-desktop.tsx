import Link from "next/link"
import { Logo } from "./logo"
import { Button } from "./button"

export const NAV_ITEMS = [
  { title: "Pricing", href: "/pricing" },
  { title: "About", href: "/about" },
  { title: "Careers", href: "/careers" },
  { title: "Blog", href: "/blog" },
] as const

export function DesktopNav({ items }: { items: ReadonlyArray<{ title: string; href: string }> }) {
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
