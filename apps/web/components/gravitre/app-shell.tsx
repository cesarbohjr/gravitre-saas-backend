"use client"

import { useState } from "react"
import { Sidebar } from "./sidebar"
import { TopBar } from "./top-bar"
import { NotificationProvider } from "./notification-center"
import { CommandPalette } from "./command-palette"
import { GoalWorkflowWizard } from "./goal-workflow-wizard"
import { useRouter } from "next/navigation"

interface AppShellProps {
  children: React.ReactNode
  title?: string
}

export function AppShell({ children, title }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [goalWizardOpen, setGoalWizardOpen] = useState(false)
  const router = useRouter()

  return (
    <NotificationProvider>
      <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopBar title={title} onMenuClick={() => setSidebarOpen(true)} />
          <main className="flex-1 overflow-y-auto">{children}</main>
        </div>
      </div>
      
      {/* Command Palette - accessible via Cmd+K */}
      <CommandPalette onCreateFromGoal={() => setGoalWizardOpen(true)} />
      
      {/* Goal Workflow Wizard */}
      <GoalWorkflowWizard
        open={goalWizardOpen}
        onOpenChange={setGoalWizardOpen}
        onBuildWorkflow={(plan) => {
          console.log("Goal plan:", plan)
          router.push("/workflows/new/builder")
        }}
      />
    </NotificationProvider>
  )
}
