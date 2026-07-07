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
        <div className="flex h-screen bg-background">
          <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          <div className="flex flex-1 flex-col overflow-hidden">
            <TopBar onMenuClick={() => setSidebarOpen(true)} />
            <main className="flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
        </div>
        <MesonToolbarPopup />
      </MesonToolbarProvider>
    </NotificationProvider>
  )
}
