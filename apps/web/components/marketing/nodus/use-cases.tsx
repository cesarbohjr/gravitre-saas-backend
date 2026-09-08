"use client";
import React, { useState } from "react";
import { Container } from "./container";
import { Badge } from "./badge";
import { SectionHeading } from "./seciton-heading";
import { SubHeading } from "./subheading";
import {
  DevopsIcon,
  PhoneIcon,
  DatabaseIcon,
  WalletIcon,
  GraphIcon,
  SparklesIcon,
} from "@/components/marketing/nodus-icons/card-icons";
import { Scale } from "./scale";
import { motion } from "framer-motion";

export const UseCases = () => {
  const useCases = [
    {
      title: "DevOps",
      description:
        "Automate deployments, incident response, and infrastructure checks — with approval gates before anything hits production.",
      icon: <DevopsIcon className="text-brand size-6" />,
    },
    {
      title: "SalesOps",
      description:
        "Sync CRM records, route leads, and coordinate follow-ups across HubSpot, Salesforce, and Slack without manual handoffs.",
      icon: <GraphIcon className="text-brand size-6" />,
    },
    {
      title: "Marketing Ops",
      description:
        "Orchestrate campaigns, route inbound leads, and sync performance data from your marketing stack — with human approval on sends and spend.",
      icon: <SparklesIcon className="text-brand size-6" />,
    },
    {
      title: "Customer Support",
      description:
        "Triage tickets, summarize conversations, and escalate with full context pulled from connected helpdesk and chat tools.",
      icon: <PhoneIcon className="text-brand size-6" />,
    },
    {
      title: "DataOps",
      description:
        "Move data between systems, monitor pipeline health, and surface anomalies before they break downstream workflows.",
      icon: <DatabaseIcon className="text-brand size-6" />,
    },
    {
      title: "FinOps",
      description:
        "Track spend signals, reconcile usage, and route approval workflows for budget changes and vendor actions.",
      icon: <WalletIcon className="text-brand size-6" />,
    },
  ];
  const [activeUseCase, setActiveUseCase] = useState<number | null>(null);
  return (
    <Container className="border-divide relative overflow-hidden border-x px-4 md:px-8">
      <div className="relative flex flex-col items-center py-20">
        <Badge text="Use Cases" />
        <SectionHeading className="mt-4">
          Across your operations
        </SectionHeading>

        <SubHeading as="p" className="mx-auto mt-6 max-w-lg">
          One shared brain coordinates agents, workflows, and people across
          departments — with governance and audit trails on every action.
        </SubHeading>

        <div className="mt-12 grid grid-cols-1 gap-10 md:grid-cols-2 lg:grid-cols-3">
          {useCases.map((useCase, index) => (
            <div
              onMouseEnter={() => setActiveUseCase(index)}
              key={useCase.title}
              className="relative"
            >
              {activeUseCase === index && (
                <motion.div
                  layoutId="scale"
                  className="absolute inset-0 z-0"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 0.5 }}
                  exit={{ opacity: 0 }}
                >
                  <Scale />
                </motion.div>
              )}
              <div className="relative z-10 rounded-lg bg-gray-50 p-4 transition duration-200 hover:bg-transparent md:p-5 dark:bg-neutral-800">
                <div className="flex items-center gap-2">{useCase.icon}</div>
                <h3 className="mt-4 mb-2 text-lg font-medium">
                  {useCase.title}
                </h3>
                <p className="text-gray-600">{useCase.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Container>
  );
};
