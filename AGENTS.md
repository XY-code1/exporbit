# Exporbit Engineering Instructions

## Product and scope

- `README.md` and the confirmed product documents in `docs/` define the product boundary.
- Preserve the existing prototype. Treat it as a validated interaction reference, not production architecture.
- Clearly label DEMO, mock, manually imported, planned, and live-provider data.
- Do not describe simulated behavior as a working external integration.

## Architecture

- Build a modular monolith: React/TypeScript frontend, FastAPI/Python backend, PostgreSQL, local file storage for MVP.
- Keep domain services independent of DeepSeek and knowledge-provider SDKs through explicit provider interfaces.
- Do not add microservices, Redis, Celery, Kubernetes, LangGraph, pgvector, or a second state-management framework without a measured requirement and an accepted decision record.
- API keys and provider credentials are server-side only. Commit only placeholders in `.env.example`.

## Data integrity

- Use explicit information states: `CONFIRMED`, `INFERRED`, `NEEDS_CONFIRMATION`, `INSUFFICIENT_DATA`, `UNAVAILABLE`.
- Human edits take precedence over AI output and must not be overwritten silently.
- Preserve communication versions, evidence provenance, original source snapshots, provider status, and audit events.
- Risk signals are not fraud determinations. Never invent precise scores without evidence.

## Delivery discipline

- Read existing code and documents before editing; avoid duplicate documents and speculative abstractions.
- Add migrations for schema changes and tests for business-critical behavior.
- Keep prototype build and Sites packaging files intact. Before changing the prototype, run `npm run build` and `npm run test:sites`.
- Do not commit `.env`, credentials, customer data, uploads, build output, or local runtime data.

