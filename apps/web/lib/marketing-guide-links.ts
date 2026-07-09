/** Canonical doc destinations for marketing guide/support cards (avoid slug guessing). */
export const MARKETING_GUIDE_LINKS: Record<string, string> = {
  "Create Your First AI Agent": "/docs/guides/how-to/agents",
  "Understanding Agent Capabilities": "/docs/guides/how-to/agents",
  "Building Multi-Step Workflows": "/docs/guides/how-to/workflows",
  "Connecting Salesforce CRM": "/docs/integrations/salesforce",
  "HubSpot Marketing Automation": "/docs/integrations/hubspot",
  "Slack Notifications & Commands": "/docs/guides/how-to/connectors",
  "Training Agents on Your Brand Voice": "/docs/guides/how-to/training",
  "Setting Up SSO/SAML Authentication": "/docs/concepts/authentication",
  "API Quickstart Guide": "/docs/api/quickstart",
  "Workflow Error Handling": "/docs/guides/how-to/failure-alerts",
  "Agent Performance Optimization": "/docs/guides/how-to/metrics",
  "Managing Team Permissions": "/docs/guides/how-to/settings",
  "Webhook Integration Patterns": "/docs/api/webhooks",
  "Conditional Logic in Workflows": "/docs/guides/how-to/workflows",
  "Data Security Best Practices": "/docs/concepts/security",
  "Scaling Agent Operations": "/docs/guides/how-to/metrics",
}

export const SUPPORT_CATEGORY_LINKS: Record<string, string> = {
  "Getting Started": "/docs/getting-started/quickstart",
  "Account & Billing": "/docs/guides/how-to/settings",
  Integrations: "/docs/integrations",
  "Security & Compliance": "/docs/concepts/security",
  Troubleshooting: "/docs/faq",
  "API & Developers": "/docs/api/swagger",
}

export const SUPPORT_POPULAR_ARTICLES: Array<{ title: string; href: string; views: string }> = [
  {
    title: "How to create your first agent",
    href: "/docs/guides/how-to/agents",
    views: "12.4k",
  },
  {
    title: "Connecting to Salesforce",
    href: "/docs/integrations/salesforce",
    views: "8.2k",
  },
  {
    title: "Understanding workflow triggers",
    href: "/docs/guides/how-to/workflows",
    views: "7.1k",
  },
  {
    title: "Managing team permissions",
    href: "/docs/guides/how-to/settings",
    views: "5.8k",
  },
  {
    title: "Troubleshooting sync errors",
    href: "/docs/faq",
    views: "5.2k",
  },
  {
    title: "Setting up SSO/SAML",
    href: "/docs/concepts/authentication",
    views: "4.9k",
  },
]

export function guideHref(title: string): string {
  return MARKETING_GUIDE_LINKS[title] ?? "/docs"
}
