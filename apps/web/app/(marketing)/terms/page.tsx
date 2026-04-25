"use client"

import { motion } from "framer-motion"

const sections = [
  {
    title: "1. Acceptance of Terms",
    content: `By accessing or using Gravitre's services, you agree to be bound by these Terms of Service and all applicable laws and regulations. If you do not agree with any of these terms, you are prohibited from using or accessing our services.

These terms apply to all visitors, users, and others who access or use our platform, including our AI Operator, workflow automation tools, and related services.`,
  },
  {
    title: "2. Description of Services",
    content: `Gravitre provides an AI-powered operations platform that enables businesses to automate workflows, deploy AI agents, and orchestrate complex business processes.

Our services include:
- AI Operator for natural language task automation
- Workflow builder and automation tools
- Agent management and orchestration
- Data source connectors and integrations
- Analytics and monitoring dashboards
- API access for custom integrations`,
  },
  {
    title: "3. Account Registration",
    content: `To access certain features of our services, you must register for an account. You agree to:

- Provide accurate, current, and complete information
- Maintain and promptly update your account information
- Keep your password secure and confidential
- Accept responsibility for all activities under your account
- Notify us immediately of any unauthorized access

We reserve the right to suspend or terminate accounts that violate these terms or engage in fraudulent activity.`,
  },
  {
    title: "4. Subscription and Billing",
    content: `**Pricing:** Our services are offered under various subscription plans as described on our pricing page. Prices are subject to change with 30 days notice.

**Billing Cycle:** Subscriptions are billed monthly or annually in advance. Annual subscriptions receive a discount as indicated at checkout.

**Cancellation:** You may cancel your subscription at any time. Cancellation takes effect at the end of the current billing period. No refunds are provided for partial periods.

**Free Trial:** Trial periods, if offered, convert to paid subscriptions unless cancelled before the trial ends.`,
  },
  {
    title: "5. Acceptable Use",
    content: `You agree not to use our services to:

- Violate any applicable laws or regulations
- Infringe on intellectual property rights of others
- Transmit malicious code, viruses, or harmful content
- Attempt to gain unauthorized access to our systems
- Interfere with or disrupt our services
- Engage in automated data scraping without permission
- Use our AI capabilities to generate harmful, illegal, or deceptive content
- Circumvent usage limits or security measures
- Resell or redistribute our services without authorization`,
  },
  {
    title: "6. Data and Privacy",
    content: `Your use of our services is also governed by our Privacy Policy, which describes how we collect, use, and protect your data.

**Your Data:** You retain ownership of all data you input into our platform. You grant us a limited license to process your data solely to provide our services.

**Data Processing:** Our AI agents and workflows may process your data according to configurations you set. You are responsible for ensuring your use of automations complies with applicable data protection laws.

**Data Security:** We implement industry-standard security measures to protect your data. See our Security page for details.`,
  },
  {
    title: "7. Intellectual Property",
    content: `**Our IP:** Gravitre and its licensors own all rights to the platform, including software, designs, trademarks, and documentation. These terms do not grant you any rights to our intellectual property except the limited license to use our services.

**Your IP:** You retain all rights to your data, workflows, and custom configurations. We do not claim ownership of content you create using our platform.

**Feedback:** If you provide suggestions or feedback, we may use it to improve our services without obligation to you.`,
  },
  {
    title: "8. Third-Party Integrations",
    content: `Our services may integrate with third-party applications (e.g., Salesforce, HubSpot, Slack). Your use of such integrations is subject to the terms of those third parties.

We are not responsible for the availability, security, or practices of third-party services. You authorize us to access and process data from connected services as necessary to provide our platform.`,
  },
  {
    title: "9. Service Level Agreement",
    content: `For customers on Growth plans and above, we commit to:

- 99.9% uptime for core platform services
- Response times for support requests based on severity
- Scheduled maintenance windows with advance notice

SLA credits may be available for qualifying downtime as described in your service agreement.`,
  },
  {
    title: "10. Limitation of Liability",
    content: `TO THE MAXIMUM EXTENT PERMITTED BY LAW, GRAVITRE SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING LOSS OF PROFITS, DATA, OR BUSINESS OPPORTUNITIES.

Our total liability for any claims arising from these terms or your use of our services shall not exceed the amount you paid us in the twelve (12) months preceding the claim.`,
  },
  {
    title: "11. Indemnification",
    content: `You agree to indemnify and hold harmless Gravitre, its officers, directors, employees, and agents from any claims, damages, or expenses arising from:

- Your use of our services
- Your violation of these terms
- Your violation of any third-party rights
- Content or data you process through our platform`,
  },
  {
    title: "12. Termination",
    content: `We may suspend or terminate your access to our services at any time for:

- Violation of these terms
- Non-payment of fees
- Fraudulent or illegal activity
- Upon your request

Upon termination, your right to use our services ceases immediately. We will provide reasonable opportunity to export your data.`,
  },
  {
    title: "13. Changes to Terms",
    content: `We may modify these terms at any time. We will notify you of material changes via email or through our platform at least 30 days before they take effect. Your continued use of our services after changes take effect constitutes acceptance of the modified terms.`,
  },
  {
    title: "14. Governing Law",
    content: `These terms shall be governed by the laws of the State of Delaware, without regard to conflict of law principles. Any disputes shall be resolved in the state or federal courts located in Delaware.`,
  },
  {
    title: "15. Contact",
    content: `For questions about these terms, please contact us at:

**Email:** legal@gravitre.com
**Address:** 548 Market St, Suite 35000, San Francisco, CA 94104`,
  },
]

export default function TermsPage() {
  return (
    <div className="bg-black">
      <section className="px-6 py-24 lg:py-32">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl font-semibold text-white mb-4">Terms of Service</h1>
            <p className="text-zinc-400 mb-2">Last updated: April 1, 2026</p>
            <p className="text-zinc-400 mb-12">
              Please read these terms carefully before using Gravitre&apos;s services.
            </p>

            <div className="space-y-10">
              {sections.map((section, i) => (
                <motion.div
                  key={section.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.03 }}
                >
                  <h2 className="text-xl font-semibold text-white mb-4">{section.title}</h2>
                  <div className="text-zinc-400 whitespace-pre-line">
                    {section.content}
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  )
}
