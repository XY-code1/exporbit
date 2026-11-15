# TradePilot

TradePilot is an AI-assisted cross-border business workspace for Chinese small and medium-sized smart-hardware and consumer-electronics exporters.

> Current status: interactive frontend MVP prototype. External AI, search, customer-research, email, database, and file-parsing services are not connected.

## Project Overview

TradePilot begins with an overseas customer inquiry and helps a salesperson understand requirements, compare the inquiry with the company's products, organize evidence, decide the next business action, and prepare a reviewed business reply.

The current repository contains the Inquiry Workspace product documentation, high-fidelity prototype, acceptance evidence, and browser-based DEMO workflow.

## Product Vision

Help an export salesperson understand:

- what the customer needs;
- what the company can provide;
- what information or capability gap remains;
- what evidence supports the next action.

TradePilot is an AI business workspace rather than an automatic email sender or a traditional CRM.

## Core Features

Implemented in the interactive prototype:

- Text inquiry import flow and PDF/image/EML upload entry points.
- Business Snapshot with `CONFIRMED`, `INFERRED`, and `NEEDS_CONFIRMATION` states.
- Multi-product matching with `MATCH`, `MISMATCH`, and `UNKNOWN`.
- Manual matching corrections and browser-local persistence.
- DEMO Zhihu knowledge research with editable business questions.
- Evidence linked to a specific business question.
- Evidence-to-Action trace from question to recommendation.
- Zhihu provider on/off degradation flow.
- Chinese/English business reply generation simulation.
- Reply editing, V1/V2 version saving, restoration, and browser-local persistence.

## Product Architecture

The confirmed product design follows three mechanisms:

1. **Progressive Intelligence** — Business Snapshot first, Business Intelligence on demand, Research & Evidence at the deepest level.
2. **Evidence-to-Action** — Business Question → Knowledge Discovery → Evidence → Business Insight → Recommended Action.
3. **Business Context Matching** — many-to-many inquiry/product relationships with item-level matching and human correction.

Current implementation:

```text
Static DEMO data
      ↓
React Inquiry Workspace prototype
      ↓
Browser localStorage for prototype persistence
```

There is no backend, database, external API integration, or production authentication in this repository.

## Tech Stack

### Adopted

- React 19
- Vite 6
- JavaScript / JSX
- CSS
- Phosphor Icons
- Node.js test runner for the Sites worker package checks

### Planned or Not Yet Selected

Backend, database, AI provider adapters, search providers, authentication, deployment infrastructure, and production file processing are not implemented or frozen by this repository. They must be selected through a separate architecture decision process.

## Quick Start

Requirements:

- Node.js 20 or newer
- npm

```bash
cd prototype
npm install
npm run dev
```

Open the local URL printed by Vite.

Verification:

```bash
npm run build
npm run test:sites
```

## Project Structure

```text
TradePilot/
├─ docs/                  Product decisions and Inquiry Workspace specifications
├─ outputs/               Reviewable acceptance reports and screenshots
├─ prototype/             Interactive React/Vite frontend prototype
│  ├─ src/                Prototype UI and interactions
│  ├─ tests/              Sites worker packaging tests
│  ├─ worker/             Static hosting worker
│  └─ scripts/            Build preparation script
├─ .env.example           Environment variable template; contains no secrets
├─ .gitignore
└─ README.md
```

`work/`, dependency folders, generated builds, local uploads, caches, and temporary files are intentionally excluded from version control.

## Roadmap

Near-term work, subject to separate approval:

- Validate real PDF, image/OCR, and EML parsing.
- Define provider interfaces for AI, Zhihu, overseas search, and customer research.
- Replace browser-local persistence with an approved secure storage design.
- Add tests for provider failures, data integrity, and critical business rules.
- Prepare a production architecture and security review.

This roadmap is not a claim that these capabilities are implemented.

## Demo Notice

All inquiry records, customer names, product records, Zhihu results, evidence, analysis, and generated replies in the prototype are **DEMO data**.

- Zhihu results are not live search results.
- External links do not prove that a result was fetched from an API.
- Certification and overseas information are illustrative, not verified compliance advice.
- No email is sent.
- No real customer inquiry or personal data should be entered into the public demo.

## License

No license has been selected. All rights are reserved until the project owner chooses and adds a license.

