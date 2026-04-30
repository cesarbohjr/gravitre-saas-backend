"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import { motion } from "framer-motion"
import { 
  ArrowLeft, 
  ArrowRight, 
  BookOpen, 
  Code, 
  Zap, 
  Bot, 
  Workflow,
  Database,
  Shield,
  Terminal,
  Clock,
  CheckCircle2,
  Copy,
  ExternalLink
} from "lucide-react"
import { useState } from "react"

// Documentation content for each page
const docsContent: Record<string, {
  title: string
  description: string
  category: string
  readTime: string
  sections: Array<{
    title: string
    content: string
    code?: string
  }>
  prevPage?: { title: string; href: string }
  nextPage?: { title: string; href: string }
}> = {
  "quickstart": {
    title: "Quickstart Guide",
    description: "Get up and running with Gravitre in under 5 minutes. This guide walks you through creating your first workflow and connecting your data.",
    category: "Getting Started",
    readTime: "5 min",
    sections: [
      {
        title: "1. Create your account",
        content: "Sign up for a Gravitre account at app.gravitre.com. You'll receive a confirmation email to verify your account. Once verified, you can access your dashboard.",
      },
      {
        title: "2. Create your first workspace",
        content: "Workspaces help you organize your workflows and team members. Navigate to Settings > Workspaces and click 'Create Workspace'. Give it a name and invite your team members.",
      },
      {
        title: "3. Connect your first data source",
        content: "Gravitre supports 50+ integrations including Salesforce, HubSpot, Slack, and more. Go to Connectors > Add Connector and select your preferred integration. Follow the OAuth flow to authorize access.",
      },
      {
        title: "4. Create your first workflow",
        content: "Navigate to Workflows > Create Workflow. Use the visual builder to drag and drop nodes, or describe what you want in natural language using the AI Operator.",
        code: `// Or use the API to create workflows programmatically
const workflow = await gravitre.workflows.create({
  name: "Lead Sync Workflow",
  trigger: {
    type: "schedule",
    cron: "0 9 * * *" // Daily at 9 AM
  },
  steps: [
    {
      type: "connector",
      connector: "salesforce",
      action: "query",
      config: {
        query: "SELECT Id, Name, Email FROM Lead WHERE CreatedDate = TODAY"
      }
    }
  ]
});`
      },
      {
        title: "5. Run and monitor",
        content: "Click 'Run Now' to execute your workflow immediately, or wait for the scheduled trigger. Monitor execution in real-time from the Runs dashboard.",
      }
    ],
    nextPage: { title: "AI Operator", href: "/docs/ai-operator" }
  },
  "ai-operator": {
    title: "AI Operator",
    description: "Learn how to use natural language to automate tasks. The AI Operator understands your intent and executes complex workflows automatically.",
    category: "Core Features",
    readTime: "8 min",
    sections: [
      {
        title: "What is the AI Operator?",
        content: "The AI Operator is Gravitre's natural language interface. Instead of manually building workflows, you can describe what you want in plain English, and the AI will create and execute the automation for you.",
      },
      {
        title: "How it works",
        content: "The AI Operator uses a multi-step process: 1) Intent Understanding - parses your request to understand the goal, 2) Planning - creates an action plan with steps, 3) Execution - runs each step with human-in-the-loop approval for sensitive actions, 4) Learning - improves based on feedback.",
      },
      {
        title: "Example prompts",
        content: "Here are some examples of what you can ask the AI Operator:",
        code: `"Sync all new leads from Salesforce to HubSpot daily"

"When a deal closes in HubSpot, create a project in Asana and notify the team in Slack"

"Generate a weekly report of our top 10 customers by revenue and email it to the sales team"

"Find all contacts who haven't been contacted in 30 days and create follow-up tasks"`
      },
      {
        title: "Action Plans",
        content: "Before executing, the AI Operator shows you the action plan for approval. You can modify steps, add conditions, or reject the plan entirely. This human-in-the-loop approach ensures safety and accuracy.",
      },
      {
        title: "API Integration",
        content: "You can also use the AI Operator programmatically via the API:",
        code: `const plan = await gravitre.operator.createPlan({
  instruction: "Sync new leads from Salesforce to HubSpot",
  context: {
    workspace_id: "ws_123",
    connectors: ["salesforce", "hubspot"]
  }
});

// Review the plan
console.log(plan.steps);

// Execute if approved
const run = await gravitre.operator.execute(plan.id);`
      }
    ],
    prevPage: { title: "Quickstart", href: "/docs/quickstart" },
    nextPage: { title: "Workflows", href: "/docs/workflows" }
  },
  "workflows": {
    title: "Workflows",
    description: "Build powerful automated workflows using our visual builder or API. Connect multiple steps, add conditions, and handle errors gracefully.",
    category: "Core Features",
    readTime: "12 min",
    sections: [
      {
        title: "Workflow Overview",
        content: "Workflows are the core of Gravitre. A workflow consists of a trigger (what starts it), steps (actions to perform), and optional conditions (branching logic). Workflows can be as simple as a two-step sync or as complex as multi-branch decision trees.",
      },
      {
        title: "Visual Builder",
        content: "The visual workflow builder lets you drag and drop nodes to create workflows. Connect nodes with edges to define the flow. Each node can be configured with specific parameters, and you can preview the workflow before saving.",
      },
      {
        title: "Triggers",
        content: "Workflows can be triggered in multiple ways:\n\n- Schedule: Run on a cron schedule (daily, weekly, etc.)\n- Webhook: Trigger via HTTP POST request\n- Event: React to events from connected integrations\n- Manual: Run on-demand from the dashboard or API",
        code: `// Schedule trigger
{
  "type": "schedule",
  "cron": "0 9 * * 1-5" // Weekdays at 9 AM
}

// Webhook trigger
{
  "type": "webhook",
  "path": "/hooks/lead-created"
}

// Event trigger
{
  "type": "event",
  "connector": "salesforce",
  "event": "lead.created"
}`
      },
      {
        title: "Steps and Actions",
        content: "Each step in a workflow performs an action. Actions include querying data, transforming data, calling APIs, sending notifications, and more. Steps can access outputs from previous steps using the {{step_name.output}} syntax.",
      },
      {
        title: "Conditions and Branching",
        content: "Add conditional logic to route workflow execution based on data values. Use if/else branches, switch statements, or filter conditions to control flow.",
        code: `// Conditional branching example
{
  "type": "condition",
  "expression": "{{lead.score}} > 80",
  "true_branch": "high_priority_path",
  "false_branch": "standard_path"
}`
      },
      {
        title: "Error Handling",
        content: "Configure error handling for each step: retry with backoff, skip and continue, or fail the entire workflow. You can also set up error notifications to alert your team when issues occur.",
      }
    ],
    prevPage: { title: "AI Operator", href: "/docs/ai-operator" },
    nextPage: { title: "Connectors", href: "/docs/connectors" }
  },
  "connectors": {
    title: "Connectors",
    description: "Connect your favorite tools and data sources. Gravitre supports 50+ integrations with more added regularly.",
    category: "Integrations",
    readTime: "10 min",
    sections: [
      {
        title: "Available Connectors",
        content: "Gravitre connects to popular business tools:\n\n**CRM**: Salesforce, HubSpot, Pipedrive\n**Communication**: Slack, Microsoft Teams, Email\n**Productivity**: Asana, Jira, Notion, Airtable\n**Data**: PostgreSQL, MySQL, Snowflake, BigQuery\n**Marketing**: Mailchimp, Sendgrid, Marketo\n**Custom**: REST API, GraphQL, Webhooks",
      },
      {
        title: "Adding a Connector",
        content: "Navigate to Connectors > Add Connector. Select the integration you want to connect. Most connectors use OAuth for authentication - you'll be redirected to authorize Gravitre to access your account.",
      },
      {
        title: "Connector Actions",
        content: "Each connector supports specific actions:\n\n- **Query**: Fetch data from the source\n- **Create**: Add new records\n- **Update**: Modify existing records\n- **Delete**: Remove records\n- **Custom**: Execute custom operations",
        code: `// Salesforce connector example
{
  "connector": "salesforce",
  "action": "query",
  "config": {
    "query": "SELECT Id, Name, Email FROM Contact WHERE LastModifiedDate > YESTERDAY"
  }
}

// Slack connector example
{
  "connector": "slack",
  "action": "send_message",
  "config": {
    "channel": "#sales-alerts",
    "message": "New lead: {{lead.name}} from {{lead.company}}"
  }
}`
      },
      {
        title: "Sync Modes",
        content: "Connectors support different sync modes:\n\n- **Full Sync**: Fetch all data each time\n- **Incremental Sync**: Only fetch new or modified data\n- **Real-time**: Stream changes as they happen",
      },
      {
        title: "Custom Connectors",
        content: "Build custom connectors for any REST or GraphQL API using our connector SDK. Define authentication, available actions, and data schemas.",
        code: `// Custom connector definition
const myConnector = {
  name: "My Custom API",
  auth: {
    type: "api_key",
    header: "X-API-Key"
  },
  actions: {
    getUsers: {
      method: "GET",
      path: "/api/users",
      response: {
        type: "array",
        items: { type: "object" }
      }
    }
  }
};`
      }
    ],
    prevPage: { title: "Workflows", href: "/docs/workflows" },
    nextPage: { title: "Introduction", href: "/docs/introduction" }
  },
  "introduction": {
    title: "Introduction to Gravitre",
    description: "Learn about Gravitre's architecture and core concepts. Understand how AI-powered automation can transform your business processes.",
    category: "Core Concepts",
    readTime: "6 min",
    sections: [
      {
        title: "What is Gravitre?",
        content: "Gravitre is an AI-powered automation platform that helps teams automate complex business processes. Unlike traditional automation tools, Gravitre uses natural language understanding and intelligent planning to create and execute workflows automatically.",
      },
      {
        title: "Key Concepts",
        content: "**Workspaces**: Organize your workflows and team members\n**Workflows**: Automated sequences of actions\n**Connectors**: Integrations with external tools and data\n**AI Operator**: Natural language interface for creating automations\n**Runs**: Individual executions of a workflow",
      },
      {
        title: "Architecture Overview",
        content: "Gravitre's architecture consists of several layers:\n\n1. **Natural Language Interface**: Understands your intent\n2. **Planning Engine**: Creates optimized action plans\n3. **Execution Layer**: Runs workflows reliably\n4. **Connector Layer**: Interfaces with external systems\n5. **Memory Layer**: Stores context and learns from feedback",
      },
      {
        title: "Use Cases",
        content: "Common use cases for Gravitre include:\n\n- **Sales Automation**: Lead scoring, CRM syncing, follow-up scheduling\n- **Marketing Operations**: Campaign management, data enrichment, reporting\n- **Customer Success**: Onboarding workflows, health scoring, renewal alerts\n- **Operations**: Data pipeline automation, system integrations, monitoring",
      }
    ],
    prevPage: { title: "Connectors", href: "/docs/connectors" },
    nextPage: { title: "Architecture", href: "/docs/architecture" }
  },
  "architecture": {
    title: "Architecture Overview",
    description: "Deep dive into Gravitre's technical architecture, including the AI planning engine, execution layer, and security model.",
    category: "Core Concepts",
    readTime: "15 min",
    sections: [
      {
        title: "System Architecture",
        content: "Gravitre is built on a modern, scalable architecture designed for reliability and performance. The system consists of several interconnected services that work together to process natural language requests, plan actions, and execute workflows.",
      },
      {
        title: "AI Planning Engine",
        content: "The planning engine is the brain of Gravitre. It uses large language models combined with structured planning algorithms to:\n\n1. Parse natural language instructions\n2. Identify required connectors and actions\n3. Generate an optimized execution plan\n4. Handle edge cases and error scenarios",
      },
      {
        title: "Execution Layer",
        content: "The execution layer handles reliable workflow execution:\n\n- **Task Queue**: Durable queue for job processing\n- **Workers**: Scalable worker pool for parallel execution\n- **State Management**: Persistent state for long-running workflows\n- **Retry Logic**: Automatic retries with exponential backoff",
      },
      {
        title: "Security Model",
        content: "Security is built into every layer:\n\n- **Encryption**: AES-256 encryption at rest, TLS 1.3 in transit\n- **Access Control**: Role-based access with fine-grained permissions\n- **Audit Logging**: Complete audit trail of all actions\n- **Compliance**: GDPR and CCPA compliant",
      }
    ],
    prevPage: { title: "Introduction", href: "/docs/introduction" },
    nextPage: { title: "Authentication", href: "/docs/authentication" }
  },
  "authentication": {
    title: "Authentication",
    description: "Learn how to authenticate with Gravitre using API keys, OAuth, or SSO. Secure your integrations with best practices.",
    category: "Core Concepts",
    readTime: "8 min",
    sections: [
      {
        title: "Authentication Methods",
        content: "Gravitre supports multiple authentication methods:\n\n- **API Keys**: For server-to-server communication\n- **OAuth 2.0**: For user-authorized integrations\n- **SSO**: SAML and OIDC for enterprise single sign-on",
      },
      {
        title: "API Keys",
        content: "Generate API keys from Settings > API Keys. Each key can be scoped to specific permissions and workspaces.",
        code: `// Using API keys
const gravitre = new Gravitre({
  apiKey: process.env.GRAVITRE_API_KEY,
  orgId: process.env.GRAVITRE_ORG_ID
});

// Or with HTTP headers
fetch('https://api.gravitre.com/v1/workflows', {
  headers: {
    'Authorization': 'Bearer YOUR_API_KEY',
    'X-Org-Id': 'YOUR_ORG_ID'
  }
});`
      },
      {
        title: "OAuth 2.0",
        content: "For applications that need to act on behalf of users, use OAuth 2.0 authorization code flow.",
        code: `// OAuth authorization URL
const authUrl = \`https://auth.gravitre.com/oauth/authorize?
  client_id=YOUR_CLIENT_ID&
  redirect_uri=YOUR_REDIRECT_URI&
  response_type=code&
  scope=workflows:read workflows:write\`;

// Exchange code for tokens
const tokens = await gravitre.oauth.exchangeCode(code);`
      },
      {
        title: "SSO Configuration",
        content: "Enterprise customers can configure SSO with SAML 2.0 or OpenID Connect. Contact support to enable SSO for your organization.",
      }
    ],
    prevPage: { title: "Architecture", href: "/docs/architecture" },
    nextPage: { title: "Workspaces", href: "/docs/workspaces" }
  },
  "workspaces": {
    title: "Workspaces & Teams",
    description: "Organize your workflows and collaborate with team members using workspaces.",
    category: "Core Concepts",
    readTime: "6 min",
    sections: [
      {
        title: "Understanding Workspaces",
        content: "Workspaces are the top-level organizational unit in Gravitre. Each workspace contains its own workflows, connectors, and team members. Use workspaces to separate different projects, teams, or environments.",
      },
      {
        title: "Creating Workspaces",
        content: "Navigate to Settings > Workspaces > Create Workspace. Provide a name and optional description. You can create unlimited workspaces on paid plans.",
      },
      {
        title: "Team Roles",
        content: "Assign roles to control access:\n\n- **Owner**: Full access, can delete workspace\n- **Admin**: Manage members and settings\n- **Editor**: Create and modify workflows\n- **Viewer**: Read-only access",
      },
      {
        title: "Environment Separation",
        content: "Best practice is to create separate workspaces for development, staging, and production. This ensures test workflows don't affect production data.",
      }
    ],
    prevPage: { title: "Authentication", href: "/docs/authentication" }
  }
}

// Fallback content for pages not yet defined
const defaultContent = {
  title: "Documentation",
  description: "This documentation page is coming soon.",
  category: "Documentation",
  readTime: "3 min",
  sections: [
    {
      title: "Coming Soon",
      content: "We're working on this documentation. Check back soon for updates, or contact support if you need immediate assistance.",
    }
  ]
}

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
      className="absolute top-3 right-3 p-2 rounded-lg bg-zinc-700 hover:bg-zinc-600 transition-colors"
    >
      {copied ? (
        <CheckCircle2 className="h-4 w-4 text-emerald-400" />
      ) : (
        <Copy className="h-4 w-4 text-zinc-400" />
      )}
    </button>
  )
}

export default function DocsSlugPage() {
  const params = useParams()
  const slug = Array.isArray(params.slug) ? params.slug.join('/') : params.slug
  const content = docsContent[slug] || defaultContent
  
  return (
    <div className="bg-white min-h-screen">
      {/* Breadcrumb and header */}
      <section className="border-b border-zinc-200 bg-zinc-50/50">
        <div className="mx-auto max-w-4xl px-6 py-8">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <Link 
              href="/docs"
              className="inline-flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900 mb-4"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Docs
            </Link>
            
            <div className="flex items-center gap-3 mb-3">
              <span className="text-xs font-medium text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full">
                {content.category}
              </span>
              <span className="flex items-center gap-1 text-xs text-zinc-500">
                <Clock className="h-3 w-3" />
                {content.readTime} read
              </span>
            </div>
            
            <h1 className="text-3xl font-semibold text-zinc-900 sm:text-4xl">
              {content.title}
            </h1>
            <p className="mt-4 text-lg text-zinc-600 max-w-3xl">
              {content.description}
            </p>
          </motion.div>
        </div>
      </section>

      {/* Content */}
      <section className="px-6 py-12">
        <div className="mx-auto max-w-4xl">
          <div className="space-y-12">
            {content.sections.map((section, i) => (
              <motion.div
                key={section.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
              >
                <h2 className="text-xl font-semibold text-zinc-900 mb-4">
                  {section.title}
                </h2>
                <div className="prose prose-zinc max-w-none">
                  {section.content.split('\n\n').map((paragraph, j) => (
                    <p key={j} className="text-zinc-600 whitespace-pre-line mb-4">
                      {paragraph}
                    </p>
                  ))}
                </div>
                {section.code && (
                  <div className="relative mt-4 rounded-xl bg-zinc-900 overflow-hidden">
                    <CopyButton text={section.code} />
                    <pre className="p-4 overflow-x-auto text-sm">
                      <code className="text-zinc-300 font-mono">{section.code}</code>
                    </pre>
                  </div>
                )}
              </motion.div>
            ))}
          </div>

          {/* Navigation */}
          <div className="mt-16 pt-8 border-t border-zinc-200">
            <div className="flex items-center justify-between">
              {content.prevPage ? (
                <Link
                  href={content.prevPage.href}
                  className="group flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900"
                >
                  <ArrowLeft className="h-4 w-4 group-hover:-translate-x-1 transition-transform" />
                  <span>
                    <span className="text-xs text-zinc-500 block">Previous</span>
                    <span className="font-medium text-zinc-900">{content.prevPage.title}</span>
                  </span>
                </Link>
              ) : <div />}
              
              {content.nextPage ? (
                <Link
                  href={content.nextPage.href}
                  className="group flex items-center gap-2 text-sm text-zinc-500 hover:text-zinc-900 text-right"
                >
                  <span>
                    <span className="text-xs text-zinc-500 block">Next</span>
                    <span className="font-medium text-zinc-900">{content.nextPage.title}</span>
                  </span>
                  <ArrowRight className="h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </Link>
              ) : <div />}
            </div>
          </div>
        </div>
      </section>

      {/* Help CTA */}
      <section className="px-6 py-12 border-t border-zinc-200 bg-zinc-50/50">
        <div className="mx-auto max-w-4xl text-center">
          <h3 className="text-lg font-medium text-zinc-900 mb-2">Need more help?</h3>
          <p className="text-sm text-zinc-500 mb-4">
            Can&apos;t find what you&apos;re looking for? Our team is here to help.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-full bg-zinc-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 transition-colors"
            >
              Contact Support
            </Link>
            <a
              href="https://github.com/gravitre"
              className="inline-flex items-center gap-2 rounded-full border border-zinc-200 px-5 py-2.5 text-sm font-medium text-zinc-900 hover:bg-zinc-50 transition-colors"
            >
              <ExternalLink className="h-4 w-4" />
              GitHub
            </a>
          </div>
        </div>
      </section>
    </div>
  )
}
