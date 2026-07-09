"use client"

import { Sidebar } from "@/components/gravitre/sidebar"
import { TopBar } from "@/components/gravitre/top-bar"
import { NotificationProvider } from "@/components/gravitre/notification-center"
import { MesonToolbarPopup, MesonToolbarProvider } from "@/components/gravitre/meson-toolbar-popup"
import { useState } from "react"

export default function LiteLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <NotificationProvider>
      <MesonToolbarProvider>
        <div className="flex h-dvh min-h-0 overflow-hidden bg-background">
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <TopBar onMenuClick={() => setSidebarOpen(true)} />
            <main className="min-h-0 flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
        </div>
        <MesonToolbarPopup />
      </MesonToolbarProvider>
    </NotificationProvider>
  )
}
