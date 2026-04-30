"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { 
  ArrowRight, 
  Code, 
  Terminal, 
  Zap, 
  Lock,
  Clock,
  Globe,
  Copy,
  Check,
  Play,
  BookOpen,
  Webhook,
  Key,
  BarChart3,
  AlertCircle
} from "lucide-react"
import { useState } from "react"

const endpoints = [
  {
    method: "POST",
    path: "/v1/agents/{id}/run",
    description: "Execute an agent with natural language instructions",
    badge: "Core",
  },
  {
    method: "GET",
    path: "/v1/runs",
    description: "List all runs with filtering and pagination",
    badge: null,
  },
  {
    method: "GET",
    path: "/v1/runs/{id}",
    description: "Get detailed status and outputs for a specific run",
    badge: null,
  },
  {
    method: "POST",
    path: "/v1/workflows/{id}/trigger",
    description: "Trigger a workflow execution programmatically",
    badge: "Core",
  },
  {
    method: "GET",
    path: "/v1/agents",
    description: "List all agents in your workspace",
    badge: null,
  },
  {
    method: "POST",
    path: "/v1/agents",
    description: "Create a new agent with configuration",
    badge: null,
  },
  {
    method: "GET",
    path: "/v1/webhooks",
    description: "List configured webhook endpoints",
    badge: null,
  },
  {
    method: "POST",
    path: "/v1/webhooks",
    description: "Register a new webhook for event notifications",
    badge: null,
  },
]

const sdks = [
  { 
    name: "Node.js", 
    install: "npm install @gravitre/sdk",
    color: "text-green-400",
    docs: "/docs/sdk/node"
  },
  { 
    name: "Python", 
    install: "pip install gravitre",
    color: "text-blue-400",
    docs: "/docs/sdk/python"
  },
  { 
    name: "Go", 
    install: "go get github.com/gravitre/go-sdk",
    color: "text-cyan-400",
    docs: "/docs/sdk/go"
  },
]

const features = [
  {
    icon: Zap,
    title: "High Performance",
    description: "Sub-100ms response times with global edge distribution",
  },
  {
    icon: Lock,
    title: "Secure by Default",
    description: "OAuth 2.0, API keys, and signed webhooks",
  },
  {
    icon: Clock,
    title: "Rate Limiting",
    description: "Generous limits with burst capacity for spikes",
  },
  {
    icon: Globe,
    title: "Global Infrastructure",
    description: "Multi-region deployment for low latency",
  },
]

const codeExample = `import { Gravitre } from '@gravitre/sdk';

const client = new Gravitre({
  apiKey: process.env.GRAVITRE_API_KEY
});

// Execute an agent
const run = await client.agents.run('agent_abc123', {
  instruction: 'Analyze Q4 sales data and create a summary report',
  context: {
    dataSource: 'salesforce',
    dateRange: '2025-Q4'
  }
});

// Wait for completion
const result = await run.wait();

console.log(result.outputs);
// { report: "Q4 Sales Summary...", metrics: {...} }`

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  
  const copy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  
  return (
    <button 
      onClick={copy}
      className="p-2 rounded-lg hover:bg-zinc-700 transition-colors"
    >
      {copied ? (
        <Check className="h-4 w-4 text-emerald-400" />
      ) : (
        <Copy className="h-4 w-4 text-zinc-400" />
      )}
    </button>
  )
}

export default function APIPage() {
  return (
    <div className="bg-background">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 py-24 lg:py-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 to-transparent" />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-emerald-100/50 rounded-full blur-3xl" />
        
        <div className="relative mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 mb-6">
              <Terminal className="h-4 w-4 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-700">REST API v1</span>
            </div>
            
            <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl">
              <span className="text-foreground">
                Build with the
              </span>
              <br />
              <span className="text-emerald-600">Gravitre API</span>
            </h1>
            
            <p className="mt-6 text-lg text-muted-foreground max-w-2xl mx-auto">
              Programmatically execute AI agents, trigger workflows, and integrate Gravitre 
              into your applications with our RESTful API.
            </p>
            
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/docs/api/quickstart"
                className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-medium text-background hover:bg-foreground/90 transition-colors"
              >
                Get Started
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/docs/api/reference"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-6 py-3 text-sm font-medium text-foreground hover:bg-muted transition-colors"
              >
                <BookOpen className="h-4 w-4" />
                API Reference
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className="px-6 py-16 border-t border-border">
        <div className="mx-auto max-w-6xl">
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="flex items-start gap-4 p-5 rounded-xl border border-border bg-muted/50"
              >
                <div className="h-10 w-10 rounded-lg bg-emerald-100 flex items-center justify-center shrink-0">
                  <feature.icon className="h-5 w-5 text-emerald-600" />
                </div>
                <div>
                  <h3 className="font-medium text-foreground">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground mt-1">{feature.description}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Code Example */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl font-bold text-foreground mb-4">Simple, powerful integration</h2>
            <p className="text-muted-foreground">Execute AI agents with just a few lines of code</p>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="relative rounded-2xl border border-zinc-200 bg-zinc-900 overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700">
              <div className="flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="h-3 w-3 rounded-full bg-red-500/80" />
                  <div className="h-3 w-3 rounded-full bg-amber-500/80" />
                  <div className="h-3 w-3 rounded-full bg-emerald-500/80" />
                </div>
                <span className="text-xs text-zinc-400 ml-2">example.ts</span>
              </div>
              <CopyButton text={codeExample} />
            </div>
            <pre className="p-6 overflow-x-auto text-sm">
              <code className="text-zinc-300 font-mono">
                {codeExample.split('\n').map((line, i) => (
                  <div key={i} className="leading-relaxed">
                    {line.includes('import') && <span className="text-purple-400">{line}</span>}
                    {line.includes('const') && !line.includes('import') && (
                      <span>
                        <span className="text-purple-400">const </span>
                        <span className="text-white">{line.replace('const ', '')}</span>
                      </span>
                    )}
                    {line.includes('await') && (
                      <span>
                        <span className="text-purple-400">await </span>
                        <span className="text-white">{line.replace(/.*await /, '')}</span>
                      </span>
                    )}
                    {line.includes('//') && <span className="text-zinc-500">{line}</span>}
                    {line.includes('console') && <span className="text-cyan-400">{line}</span>}
                    {!line.includes('import') && !line.includes('const') && !line.includes('await') && !line.includes('//') && !line.includes('console') && (
                      <span className="text-zinc-300">{line}</span>
                    )}
                  </div>
                ))}
              </code>
            </pre>
          </motion.div>
        </div>
      </section>

      {/* Endpoints */}
      <section className="px-6 py-20 border-t border-border">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="flex items-center justify-between mb-8"
          >
            <h2 className="text-2xl font-bold text-foreground">API Endpoints</h2>
            <Link 
              href="/docs/api/reference"
              className="text-sm text-emerald-600 hover:text-emerald-500 flex items-center gap-1"
            >
              Full reference
              <ArrowRight className="h-4 w-4" />
            </Link>
          </motion.div>
          
          <div className="space-y-3">
            {endpoints.map((endpoint, i) => (
              <motion.div
                key={endpoint.path}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.05 }}
                className="group flex items-center gap-4 p-4 rounded-xl border border-border bg-muted/50 hover:border-emerald-500/50 transition-colors cursor-pointer"
              >
                <span className={`
                  px-2 py-1 rounded text-xs font-mono font-semibold shrink-0
                  ${endpoint.method === 'GET' ? 'bg-blue-100 text-blue-600' : 'bg-emerald-100 text-emerald-600'}
                `}>
                  {endpoint.method}
                </span>
                <code className="text-sm text-foreground font-mono">{endpoint.path}</code>
                {endpoint.badge && (
                  <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
                    {endpoint.badge}
                  </span>
                )}
                <span className="text-sm text-muted-foreground ml-auto hidden sm:block">{endpoint.description}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* SDKs */}
      <section className="px-6 py-20 border-t border-border">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-3xl font-bold text-foreground mb-4">Official SDKs</h2>
            <p className="text-muted-foreground">Type-safe clients for your favorite languages</p>
          </motion.div>
          
          <div className="grid gap-4 sm:grid-cols-3">
            {sdks.map((sdk, i) => (
              <motion.div
                key={sdk.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.1 }}
                className="p-6 rounded-xl border border-border bg-muted/50"
              >
                <h3 className={`text-lg font-semibold ${sdk.color.replace('400', '600')} mb-3`}>{sdk.name}</h3>
                <div className="flex items-center gap-2 p-3 rounded-lg bg-zinc-900 border border-zinc-800 mb-4">
                  <code className="text-xs text-zinc-400 font-mono flex-1 truncate">{sdk.install}</code>
                  <CopyButton text={sdk.install} />
                </div>
                <Link
                  href={sdk.docs}
                  className="text-sm text-emerald-600 hover:text-emerald-500 flex items-center gap-1"
                >
                  Documentation
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Webhooks & Events */}
      <section className="px-6 py-20 border-t border-border">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-8 lg:grid-cols-2">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              className="p-8 rounded-2xl border border-border bg-gradient-to-br from-purple-50 to-background"
            >
              <div className="h-12 w-12 rounded-xl bg-purple-100 flex items-center justify-center mb-6">
                <Webhook className="h-6 w-6 text-purple-600" />
              </div>
              <h3 className="text-xl font-bold text-foreground mb-3">Webhooks</h3>
              <p className="text-muted-foreground mb-6">
                Receive real-time notifications when runs complete, workflows trigger, or errors occur. 
                All webhooks are signed for security.
              </p>
              <Link
                href="/docs/api/webhooks"
                className="inline-flex items-center gap-2 text-purple-600 hover:text-purple-500"
              >
                Configure webhooks
                <ArrowRight className="h-4 w-4" />
              </Link>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }}
              className="p-8 rounded-2xl border border-border bg-gradient-to-br from-amber-50 to-background"
            >
              <div className="h-12 w-12 rounded-xl bg-amber-100 flex items-center justify-center mb-6">
                <Key className="h-6 w-6 text-amber-600" />
              </div>
              <h3 className="text-xl font-bold text-foreground mb-3">Authentication</h3>
              <p className="text-muted-foreground mb-6">
                Secure API access with scoped API keys or OAuth 2.0. 
                Fine-grained permissions let you control exactly what each integration can access.
              </p>
              <Link
                href="/docs/api/authentication"
                className="inline-flex items-center gap-2 text-amber-600 hover:text-amber-500"
              >
                Authentication guide
                <ArrowRight className="h-4 w-4" />
              </Link>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Rate Limits */}
      <section className="px-6 py-20 border-t border-border">
        <div className="mx-auto max-w-4xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="p-8 rounded-2xl border border-border bg-muted/50"
          >
            <div className="flex items-start gap-4 mb-6">
              <div className="h-10 w-10 rounded-lg bg-emerald-100 flex items-center justify-center shrink-0">
                <BarChart3 className="h-5 w-5 text-emerald-600" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-foreground mb-2">Rate Limits</h3>
                <p className="text-muted-foreground">Generous limits designed for production workloads</p>
              </div>
            </div>
            
            <div className="grid gap-4 sm:grid-cols-3">
              {[
                { plan: "Starter", limit: "100 req/min", burst: "200 req/min" },
                { plan: "Growth", limit: "1,000 req/min", burst: "2,000 req/min" },
                { plan: "Enterprise", limit: "Custom", burst: "Unlimited" },
              ].map((tier) => (
                <div key={tier.plan} className="p-4 rounded-xl bg-background border border-border">
                  <div className="text-sm text-muted-foreground mb-1">{tier.plan}</div>
                  <div className="text-lg font-semibold text-foreground">{tier.limit}</div>
                  <div className="text-xs text-muted-foreground mt-1">Burst: {tier.burst}</div>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-20 border-t border-border">
        <div className="mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl font-bold text-foreground mb-4">Ready to build?</h2>
            <p className="text-muted-foreground mb-8">
              Get your API key and start integrating Gravitre in minutes.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/get-started"
                className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-8 py-3 text-sm font-medium text-white hover:bg-emerald-500 transition-colors"
              >
                Get API Key
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/docs/api/quickstart"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-8 py-3 text-sm font-medium text-foreground hover:bg-muted transition-colors"
              >
                <Play className="h-4 w-4" />
                Quickstart Guide
              </Link>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
