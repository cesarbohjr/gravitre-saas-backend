"use client"

import { motion } from "framer-motion"

const sections = [
  {
    title: "Information We Collect",
    content: `We collect information you provide directly to us, such as when you create an account, use our services, or contact us for support.

**Account Information:** When you register, we collect your name, email address, company name, and password.

**Usage Data:** We automatically collect information about how you use our services, including your IP address, browser type, operating system, pages visited, and actions taken within the platform.

**Integration Data:** When you connect third-party services (like Salesforce or HubSpot), we access data from those services as authorized by you to perform automations.`,
  },
  {
    title: "How We Use Your Information",
    content: `We use the information we collect to:

- Provide, maintain, and improve our services
- Process transactions and send related information
- Send technical notices, updates, security alerts, and support messages
- Respond to your comments, questions, and customer service requests
- Monitor and analyze trends, usage, and activities
- Detect, investigate, and prevent security incidents
- Personalize and improve your experience`,
  },
  {
    title: "Information Sharing",
    content: `We do not sell your personal information. We may share your information in the following circumstances:

**Service Providers:** We share information with vendors and service providers who need access to perform services on our behalf.

**Legal Requirements:** We may disclose information if required by law or if we believe disclosure is necessary to protect our rights or the safety of others.

**Business Transfers:** In connection with a merger, acquisition, or sale of assets, your information may be transferred as a business asset.`,
  },
  {
    title: "Data Security",
    content: `We implement appropriate technical and organizational measures to protect your personal information, including:

- Encryption of data in transit and at rest (AES-256)
- Regular security assessments and penetration testing
- Access controls and audit logging
- SOC 2 Type II certification
- GDPR and CCPA compliance programs

While we strive to protect your information, no method of transmission over the Internet is 100% secure.`,
  },
  {
    title: "Data Retention",
    content: `We retain your information for as long as your account is active or as needed to provide you services. We will retain and use your information as necessary to comply with our legal obligations, resolve disputes, and enforce our agreements.

You may request deletion of your account and associated data at any time by contacting us at privacy@gravitre.com.`,
  },
  {
    title: "Your Rights",
    content: `Depending on your location, you may have certain rights regarding your personal information:

- **Access:** Request a copy of the personal information we hold about you
- **Correction:** Request correction of inaccurate personal information
- **Deletion:** Request deletion of your personal information
- **Portability:** Request a copy of your data in a structured, machine-readable format
- **Opt-out:** Opt out of certain data processing activities

To exercise these rights, contact us at privacy@gravitre.com.`,
  },
  {
    title: "Cookies and Tracking",
    content: `We use cookies and similar tracking technologies to collect and track information about your use of our services. You can control cookies through your browser settings.

**Essential Cookies:** Required for the platform to function properly.

**Analytics Cookies:** Help us understand how visitors interact with our website.

**Marketing Cookies:** Used to deliver relevant advertisements (only with your consent).`,
  },
  {
    title: "International Data Transfers",
    content: `Your information may be transferred to and processed in countries other than your own. We ensure appropriate safeguards are in place, including Standard Contractual Clauses approved by the European Commission.`,
  },
  {
    title: "Changes to This Policy",
    content: `We may update this privacy policy from time to time. We will notify you of any changes by posting the new policy on this page and updating the "Last updated" date.`,
  },
  {
    title: "Contact Us",
    content: `If you have any questions about this privacy policy or our data practices, please contact us at:

**Email:** privacy@gravitre.com
**Address:** 548 Market St, Suite 35000, San Francisco, CA 94104
**Data Protection Officer:** dpo@gravitre.com`,
  },
]

export default function PrivacyPage() {
  return (
    <div className="bg-white">
      <section className="px-6 py-24 lg:py-32">
        <div className="mx-auto max-w-3xl">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <h1 className="text-4xl font-semibold text-zinc-900 mb-4">Privacy Policy</h1>
            <p className="text-zinc-500 mb-2">Last updated: April 1, 2026</p>
            <p className="text-zinc-600 mb-12">
              This privacy policy describes how Gravitre Inc. (&quot;we&quot;, &quot;our&quot;, or &quot;us&quot;) collects, 
              uses, and shares information about you when you use our services.
            </p>

            <div className="space-y-12">
              {sections.map((section, i) => (
                <motion.div
                  key={section.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.05 }}
                >
                  <h2 className="text-xl font-semibold text-zinc-900 mb-4">{section.title}</h2>
                  <div className="prose prose-zinc max-w-none">
                    {section.content.split('\n\n').map((paragraph, j) => (
                      <p key={j} className="text-zinc-600 whitespace-pre-line mb-4">
                        {paragraph}
                      </p>
                    ))}
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
