"use client"

import { useState, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"

const stats = [
  { label: "Tasks Completed", value: "47", change: "+12", trend: "up", period: "this week" },
  { label: "Deliverables Created", value: "156", change: "+34", trend: "up", period: "this month" },
  { label: "Average Confidence", value: "91%", change: "+3%", trend: "up", period: "vs last month" },
  { label: "Time Saved", value: "23h", change: "+5h", trend: "up", period: "this week" },
]

const recentResults = [
  {
    date: "Today",
    items: [
      { title: "Q3 Campaign Emails", type: "emails", confidence: 94, agent: "Marketing Agent" },
      { title: "Enterprise Lead Segment", type: "segment", confidence: 88, agent: "Sales Agent" },
    ]
  },
  {
    date: "Yesterday",
    items: [
      { title: "Weekly Performance Report", type: "report", confidence: 92, agent: "Analytics Agent" },
      { title: "Social Media Content Pack", type: "social", confidence: 89, agent: "Marketing Agent" },
      { title: "Competitor Analysis", type: "report", confidence: 91, agent: "Research Agent" },
    ]
  },
  {
    date: "This Week",
    items: [
      { title: "Product Launch Emails", type: "emails", confidence: 95, agent: "Marketing Agent" },
      { title: "Q2 Retrospective Report", type: "report", confidence: 87, agent: "Analytics Agent" },
    ]
  },
]

const typeIcons = {
  emails: "mail",
  segment: "users",
  report: "file",
  social: "share",
}

export default function LiteResultsPage() {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background/95 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-6">
          <h1 className="text-2xl font-bold text-foreground">Results</h1>
          <p className="text-muted-foreground text-sm">Track your AI team&apos;s performance</p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
          {stats.map((stat, index) => (
            <Card 
              key={stat.label}
              className={cn(
                "p-5 border-border/50 transition-all duration-500",
                mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
              )}
              style={{ transitionDelay: `${index * 100}ms` }}
            >
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-2">{stat.label}</p>
              <div className="flex items-end justify-between">
                <div>
                  <p className="text-3xl font-bold text-foreground">{stat.value}</p>
                  <div className="flex items-center gap-1 mt-1">
                    <span className={cn(
                      "text-xs font-medium",
                      stat.trend === "up" ? "text-emerald-500" : "text-red-500"
                    )}>
                      {stat.change}
                    </span>
                    <Icon 
                      name={stat.trend === "up" ? "trendUp" : "trendDown"} 
                      size="xs" 
                      className={stat.trend === "up" ? "text-emerald-500" : "text-red-500"} 
                    />
                    <span className="text-xs text-muted-foreground">{stat.period}</span>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {/* Recent Results Timeline */}
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-6">
            Recent Results
          </h2>
          
          <div className="space-y-8">
            {recentResults.map((group, groupIndex) => (
              <div 
                key={group.date}
                className={cn(
                  "transition-all duration-500",
                  mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
                )}
                style={{ transitionDelay: `${(groupIndex + 4) * 100}ms` }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                  <h3 className="text-sm font-medium text-foreground">{group.date}</h3>
                  <div className="flex-1 h-px bg-border" />
                </div>
                
                <div className="ml-5 pl-5 border-l border-border/50 space-y-3">
                  {group.items.map((item, index) => (
                    <Card key={index} className="p-4 border-border/50 hover:border-border transition-colors cursor-pointer group">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center shrink-0 group-hover:bg-emerald-500/10 transition-colors">
                          <Icon 
                            name={typeIcons[item.type as keyof typeof typeIcons] as any} 
                            size="md" 
                            className="text-muted-foreground group-hover:text-emerald-500 transition-colors" 
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium text-foreground group-hover:text-emerald-500 transition-colors">
                            {item.title}
                          </h4>
                          <p className="text-xs text-muted-foreground">{item.agent}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <div className="text-sm font-semibold text-foreground">{item.confidence}%</div>
                            <div className="text-[10px] text-muted-foreground">confidence</div>
                          </div>
                          <Badge variant="outline" className="text-emerald-500 border-emerald-500/30">
                            <Icon name="check" size="xs" className="mr-1" />
                            Complete
                          </Badge>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
