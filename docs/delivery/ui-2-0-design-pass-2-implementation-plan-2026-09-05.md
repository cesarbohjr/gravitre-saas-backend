# Design Pass 2 — Reference + Implementation Audit (revised)

**Date:** 2026-09-05  
**Status:** Craft remediation after Cesar visual feedback (Agenforce live preview)  
**Live:** https://gravitre.app/  
**Scope:** Marketing homepage pilot — visual material only

## Cesar feedback (screenshots)

| Issue | Root cause | Fix |
|-------|------------|-----|
| Black text on black | How-it-works / showcase / GIBE cards used `bg-foreground` + `text-foreground` | Surfaces → `bg-card` / `--g-surface-*` |
| Green CTAs become black | Desktop Download used `bg-foreground text-white` | → `bg-primary text-primary-foreground` |
| Old light SaaS canvas | MarketingChrome forced light feel (`data-theme="light"`) vs Agenforce dark craft | Force `dark` graphite marketing shell |
| Yellow theme | Unsigned build amber pills/boxes + yellow traffic lights + amber accents | Graphite note surfaces; muted chrome dots; semantic emerald/violet/signal |
| Partial desktop windows | Flat cut-off mocks | Soft bottom mask fade (Agenforce principle) on ProductPreview + DesktopCompanion |

## Access honesty

Agenforce craft check via **PUBLIC PREVIEW** (`ui.aceternity.com/template-preview/agenforce-marketing-template` + live template). Not licensed source.

## Deploy chain

| Commit | Note |
|--------|------|
| `38060781` | Pass 2 material |
| `4981adf5` | Light wash v1 |
| `dbaca24b` | Light wash without blur |
| *(next)* | Dark canvas + contrast/yellow/button remediation |

## Explicit non-claims

No layout/copy/IA change. No invented prices/TRAINED/fake metrics. Emerald remains execute CTA (not Agenforce white transplant).
