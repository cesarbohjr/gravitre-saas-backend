"use client";
import React from "react";
import { Container } from "../container";
import { Badge } from "../badge";
import { SubHeading } from "../subheading";
import { SectionHeading } from "../seciton-heading";
import { Card, CardDescription, CardTitle } from "./card";
import {
  BrainIcon,
  FingerprintIcon,
  MouseBoxIcon,
  NativeIcon,
  RealtimeSyncIcon,
  SDKIcon,
} from "@/components/marketing/nodus-icons/bento-icons";
import {
  LLMModelSelectorSkeleton,
  NativeToolsIntegrationSkeleton,
  TextToWorkflowBuilderSkeleton,
} from "./skeletons";

type Tab = {
  title: string;
  description: string;
  icon: React.FC<React.SVGProps<SVGSVGElement>>;
  id: string;
};

export const AgenticIntelligence = () => {
  return (
    <Container className="border-divide overflow-x-hidden border-x">
      <div className="flex flex-col items-center px-4 py-16 md:px-0">
        <Badge text="Features" />
        <SectionHeading className="mt-4 px-2">
          Built for Agentic Intelligence
        </SectionHeading>

        <SubHeading as="p" className="mx-auto mt-6 max-w-lg px-2">
          Build, connect, and govern AI agents from one visual workspace —
          scoped to your org with approval gates on every write.
        </SubHeading>
        <div className="border-divide divide-divide mt-16 grid w-full grid-cols-1 divide-y border-y md:grid-cols-2 md:divide-x">
          <Card className="overflow-hidden mask-b-from-80%">
            <div className="flex min-w-0 items-center gap-2">
              <BrainIcon className="shrink-0" />
              <CardTitle>LLM Model Selector</CardTitle>
            </div>
            <CardDescription>
              Route each step to the right model — OpenAI, Anthropic, Llama,
              and more — with org-level defaults and per-workflow overrides.
            </CardDescription>
            <LLMModelSelectorSkeleton />
          </Card>
          <Card className="overflow-hidden mask-b-from-80%">
            <div className="flex min-w-0 items-center gap-2">
              <MouseBoxIcon className="shrink-0" />
              <CardTitle>Text to workflow builder</CardTitle>
            </div>
            <CardDescription>
              Describe what you want in plain language and Gravitre drafts
              agents, steps, and connector actions for your review.
            </CardDescription>
            <TextToWorkflowBuilderSkeleton />
          </Card>
        </div>
        <div className="w-full min-w-0">
          <Card className="relative w-full max-w-none overflow-hidden">
            <div className="pointer-events-none absolute inset-0 h-full w-full bg-[radial-gradient(var(--color-dots)_1px,transparent_1px)] mask-radial-from-10% [background-size:10px_10px]"></div>
            <div className="relative z-10 flex min-w-0 items-center gap-2">
              <NativeIcon className="shrink-0" />
              <CardTitle>Native Tools Integration</CardTitle>
            </div>
            <CardDescription className="relative z-10">
              Agents call HubSpot, Slack, Salesforce, and your stack through
              verified connectors — not mock APIs or placeholder integrations.
            </CardDescription>
            <div className="relative z-10 min-w-0">
              <NativeToolsIntegrationSkeleton />
            </div>
          </Card>
        </div>
        <div className="grid w-full grid-cols-1 gap-10 md:grid-cols-3">
          <Card>
            <div className="flex min-w-0 items-center gap-2">
              <FingerprintIcon className="shrink-0" />
              <CardTitle>One Click Auth</CardTitle>
            </div>
            <CardDescription>
              Connect OAuth integrations in minutes with live scope and health
              checks before anything runs in production.
            </CardDescription>
          </Card>
          <Card>
            <div className="flex min-w-0 items-center gap-2">
              <RealtimeSyncIcon className="shrink-0" />
              <CardTitle>Realtime Sync</CardTitle>
            </div>
            <CardDescription>
              Agents share context and hand off tasks in real time — coordinated
              through one business brain, not isolated chatbots.
            </CardDescription>
          </Card>
          <Card>
            <div className="flex min-w-0 items-center gap-2">
              <SDKIcon className="shrink-0" />
              <CardTitle>Custom Connector SDK</CardTitle>
            </div>
            <CardDescription>
              Build private connectors for internal APIs and proprietary systems
              with the same governance as native integrations.
            </CardDescription>
          </Card>
        </div>
      </div>
    </Container>
  );
};
