import dynamic from "next/dynamic"
import { Container } from "./container"
import { DesktopNav, NAV_ITEMS } from "./navbar-desktop"

const FloatingNav = dynamic(
  () => import("./navbar-floating").then((m) => ({ default: m.FloatingNav })),
  { ssr: false },
)

const MobileNav = dynamic(
  () => import("./navbar-mobile").then((m) => ({ default: m.MobileNav })),
  { ssr: false },
)

/** Marketing header — desktop nav SSR; scroll/mobile chrome lazy-loaded. */
export function Navbar() {
  return (
    <Container as="nav" className="">
      <DesktopNav items={NAV_ITEMS} />
      <FloatingNav items={NAV_ITEMS} />
      <MobileNav items={NAV_ITEMS} />
    </Container>
  )
}
