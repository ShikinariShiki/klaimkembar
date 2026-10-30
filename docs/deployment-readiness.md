# Deployment readiness for KlaimKembar

Status: deployment design only. The current application is a local synthetic-data prototype and this document does not establish that it is safe or functional on a public host.

## Existing constraints

- `klaimkembar/local_ui.py` creates an in-memory session and deliberately checks for a loopback request. Do not disable those checks or enable `LOCAL_UI` for an internet-facing deployment. Public access requires a proper identity and session mechanism, authorization, HTTPS-only cookies, CSRF and origin controls.
- `klaimkembar/database.py` uses local SQLite, SQLite SQL, pragmas and an append-only trigger. A Vercel Function instance's filesystem cannot serve as a durable shared database across invocations. A migration to PostgreSQL requires translating queries and migrations and verifying transactions, optimistic concurrency, review idempotency and audit triggers against PostgreSQL.
- Existing upload limit is 5 MiB. Vercel Functions cap request and response payloads at 4.5 MB, including multipart overhead; configure a lower tested limit or implement authenticated direct-to-storage upload, validation and cleanup. Source: https://vercel.com/docs/functions/limitations.
- A Vercel FastAPI deployment runs as a Function and inherits its runtime constraints; validate asset routing, bundle paths, startup, request duration and memory. Source: https://vercel.com/docs/frameworks/backend/fastapi.
- Supabase recommends its transaction pooler for serverless clients, with prepared statements disabled when using this mode, TLS required and per-instance connections constrained. Migrations should use a suitable direct or session connection. Source: https://supabase.com/docs/guides/database/connecting-to-postgres.

## Isolated synthetic demo path

1. Create a dedicated Vercel project and dedicated Supabase project or explicitly isolated resources. Do not reuse the unrelated existing `piechang-base` resource or suspended `ReLock-DB` for this app. Confirm project and billing context before creating paid resources.
2. Provision secrets in hosting project settings, never commit credentials. Configure a trusted public origin, HTTPS, bounded request size, no real JKN inputs and a synthetic-data-only visible label.
3. Implement and validate Postgres migrations with least-privilege application role; explicitly deny public data API access unless required and apply appropriate RLS and role checks. Keep service keys server-side. Ensure all calls use authorization and audit accesses.
4. Replace the in-memory loopback-only session mechanism with proper authenticated sessions suitable for horizontally scaled Functions. Do not expose internal reviewer/auditor bearer tokens to the browser.
5. Verify application flow with synthetic fixtures: upload, queue, comparison, three review decisions, idempotent retry, stale update, reload, audit retention, fallback, and access denial. Verify isolation between concurrent users, cold starts and instances.
6. Deploy a preview first; run automated checks and browser smoke tests against it. Promote to production only after tests and security controls pass. Record deployment ID, commit, rollback steps and known limitations.

## Real data and ML

Do not use real health claims or call a model trained on them until data authorization, schema and label feasibility, independent evaluation, domain review and security gates are satisfied. A public synthetic demo is not evidence of readiness for a real-data pilot or calibrated ML performance.

## Provisioning state 30 October 2026

A dedicated Vercel project `klaimkembar-demo` and dedicated Supabase marketplace resource `klaimkembar-demo` were created in `pienuts-projects` using the Supabase `free` plan and `sin1` region. The resource is connected to the Vercel project's preview and production environments; Vercel integration listing reports it as available. This verifies only control-plane provisioning and connection, not database credentials, network connectivity, migrations, data persistence, authorization, runtime behavior, or application deployment. No other project's resource was modified.
