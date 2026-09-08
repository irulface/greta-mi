# Validation record

- TypeScript: `npx tsc --noEmit` — passed.
- Frontend static export: `npm run build` — passed; output verified at `dist/client/index.html`.
- Backend: 90 API/business-rule tests passed against an isolated PostgreSQL 18 database; 84 passed on isolated SQLite, with six PostgreSQL concurrency tests skipped. Test databases are separate from the application database; the temporary PostgreSQL database was removed after testing.
- Integration contracts: Azure REST v1 request/authentication and authorized RAG evidence tested with HTTP transport mocks; MCP initialize/session/tools-call sequence tested with a transport mock.
- Local same-origin integration: session login, workspace retrieval, and safe Admin SMTP configuration retrieval passed through the frontend proxy with PostgreSQL active.
- File pipeline: upload, worker parsing, document retrieval, download, and checksum deduplication tested.
- Security: RBAC, cross-region denial, restricted document denial, CSRF origin denial, encrypted secrets, endpoint allowlists, forbidden MCP parameters, and final-response immutability tested.
- Browser visual/interaction QA has not been performed; no such validation is claimed.
- PostgreSQL is now connected and tested. Docker/Ubuntu, live Azure OpenAI, and live enterprise MCP still require integration acceptance.
- `npm run lint` is not clean: the existing frontend/component set reports strict typing, React effect, and accessibility rules. TypeScript compilation and the production build pass; lint is recorded as a remaining code-quality task, not a passed check.

## PostgreSQL migration — 2026-09-08

- Active database: `gretamidb` at `localhost:5432`; application role: `gretami`, not a superuser. Local authentication succeeds without a password; role permissions were not elevated.
- pgvector 0.8.6 enabled using the available local database administrator; application migrations and runtime use `gretami`.
- Alembic `0002` applied. Initial/full upgrade independently verified in a temporary PostgreSQL database, including GIN full-text and HNSW vector indexes.
- SQLite migration preserved and verified contents of every row: 37 records, 4 users, 4 document chunks, 4 login sessions, 7 audit events, 1 configuration; email outbox initially empty. Later normal activity can change these counts.
- Snapshot: `backend/data/backups/greta-before-postgres-20260908T022825625257Z.db`; original SQLite retained. Document files and encryption key remain in their existing data directory.
- Active `/health/ready` returns `{"status":"ok","database":"postgresql"}`. No synthetic integration-test RFI or supplier was added to the application database.

## SMTP — 2026-09-08

- Live connection and authentication passed for `asia.emailarray.com:465`, SSL with certificate verification, sender `admin@greta.id`, timeout 15 seconds. Authentication check completed in approximately 4.4 seconds; no email was sent.
- Local credentials stored in ignored `backend/.env` with mode `0600`. API returns only safe configuration fields, never SMTP credentials.
- Mocked tests cover SSL and STARTTLS, safe connection test, missing/invalid public URL, role and region checks, recipient validation, encrypted queue body, working supplier response links, repeated-click idempotency, explicit retry after confirmed failure, ambiguous delivery without automatic retry, QUIT failure after SMTP acceptance, and cancellation after invitation revocation.
- PostgreSQL concurrency test verifies simultaneous enqueue requests and two workers still produce one invitation email.
- Test fixtures block real SMTP connections. The application outbox remains empty; no mail was sent during migration or integration tests.
- `PUBLIC_APP_URL` remains unset pending the supplier-accessible HTTPS application address. Sending invitations is blocked until that address is configured. Actual inbox delivery and bounce handling have not been validated.

## Phase 2 validation — 2026-09-08

- Alembic `0003` applied on the local application database. Full upgrades also passed in isolated PostgreSQL test databases.
- Real EIA API v2 connection passed; 120 monthly Brent observations imported, latest period August 2026. Provider API key is not required for the initial manual exploration; regular scheduled EIA imports require the organization's key.
- The running worker processed a durable manual brief job to `COMPLETED`. The resulting evidence brief was shared with the Analyst and pinned with the Brent chart in the Buyer-owned **Energy market watch** workspace.
- A 24-hour brief schedule is prepared in paused state. A Buyer-owned 10% MoM increase rule monitors the sourced Brent series. No email was queued or sent.
- New tests cover date-based calculations, zero/insufficient baselines, atomic CSV/XLSX imports, formula rejection/safe CSV export, corrections, currency/unit compatibility, common-date comparisons, analyst-only landscape approval, shared workspace scope/version conflicts, brief sharing/revocation, source permission rechecks, AI citation ID rejection, alert deduplication and region filtering, EIA/JSON contracts and encrypted tokens, scheduler claim/run/failure states, advanced RFI numeric deviations, and concurrent observation writes.
- TypeScript and frontend production build pass. Build emits a bundle-size warning; no browser performance or visual QA is claimed. Earlier lint findings remain open.

## Deployment target

The deliverable is the local application and Ubuntu deployment package specified in the PRD. No production service or private enterprise data has been published. A Cloudflare Sites static deployment cannot run the required Python API/PostgreSQL stack; a static frontend alone is not a working deployment of this application. Deployment requires the supplied backend/worker/database services and organization-provided integrations.
- Earlier Alembic initial migration also executed successfully against a separate temporary SQLite database (`0001` at that time).

- Dependency audit after compatible updates: `npm audit` reports 0 vulnerabilities.

## Phase 3 validation — 2026-09-08

- Full migrations through `0004` passed in a disposable PostgreSQL database; migration applied to `gretamidb` after a mode-0600 pg_dump snapshot. New supplier identities/sessions and workflow delivery tables are available.
- 24 additional tests cover Decimal cost/FX and margins, immutable revisions/scenarios, transitive source sharing/revocation including Phase 2 reference routes, forecasting backtest/cutoff/missing periods/seasonality/intervals, risk evidence coverage/expiry/approval, and demo-data exclusion from live recommendations.
- Portal tests verify one-use activation, password hashing, separate internal/supplier sessions, company isolation, invitation and expiry checks, final submission locking, attachment isolation, draft/history/amendments, company-profile whitelist, private clarification, account/session revocation, and concurrent activation/submission.
- Enterprise tests cover encrypted tokens, HTTPS/host/public-DNS restrictions, pinned-IP connection with original TLS hostname, MCP handshake/session/tool allowlist/argument schema, JSON/SSE results, private/shared evidence, explicit Buyer approvals, encrypted delivery payload, receipt matching, timeout reconciliation, connector revocation, and concurrent queue idempotency. Tests use mocks; no live workflow or external MCP action was performed.
- Live HTTP through frontend port 3000 verified the updated app, PostgreSQL readiness, advanced-analysis authentication, supplier identity isolation, Buyer-only portal administration, and Analyst read access to the new real-data forecast.
- Saved **Brent crude — EIA monthly — forecast** as a Buyer-owned draft using 120 observations and six future periods. Backtesting selected the naïve baseline. No invented supplier assessment or organization cost assumptions were inserted.
- TypeScript and production build pass. Bundle-size warning remains; browser visual testing and organization UAT have not been performed. External MCP/workflow endpoints and credentials are still required for live integration acceptance.

- Targeted lint passed for all four new Phase 3 frontend components. Supplier activation also revokes any prior supplier session in the activating browser; the additional cross-company session test passed. Final totals: 66 PostgreSQL passed; 61 SQLite passed, 5 PostgreSQL-only tests skipped.


## Phase 4 validation — 2026-09-08

- Migration `0005` adds `agent_runs` and was applied to `gretamidb` using the existing `gretami` role. Snapshot: `backend/data/backups/greta-before-phase4-20260908T054053Z.dump`, mode 0600. A companion manifest stores per-row checksums for preservation verification; environment credentials were not changed.
- 24 additional Phase 4 tests pass. Final totals: **90 PostgreSQL passed; 84 SQLite passed, six PostgreSQL-only tests skipped**. Full migrations through 0005 pass in a disposable PostgreSQL database, removed after testing.
- Tests cover initial baseline/no fabricated changes; demand +18%, inventory 2.3 months and lead time +25% producing MEDIUM→HIGH; all eight evidence domains; record checksums; absent/stale/regressed/low-confidence and unreliable historical observations; zero baselines; same-date corrections and recurring change episodes; unit-basis changes; risk changes when the observation period rolls forward; atomic imports; demo exclusion; and source limits.
- Access and execution tests cover owner-only writes, sharing and revocation, revoked upstream evidence, Admin/requester isolation, config revision conflicts, pending cancellation, cancellation during MCP reads, region Admin stop, deadlines, interrupted-worker lease recovery, scheduled-run idempotency, inactive owners, and simultaneous enqueue/worker claims on PostgreSQL.
- Internal MCP uses fixed read tools, typed category/region/metric/date/unit contracts, enforced identity arguments, per-call response budgets, runtime host allowlist checks, and outage recovery without treating missing values as zero. Calls are mocked in tests; enterprise MCP is not connected live.
- TypeScript, targeted lint for the new Autonomous Intelligence component, and the frontend production build pass. Existing bundle-size warning and baseline lint findings remain. Browser visual QA, load/security acceptance, policy calibration and organization UAT remain open.
- The local API, frontend, existing indexing/workflow worker and new dedicated agent worker are running. HTTP verification through port 3000 checks readiness, authentication, agent creation, run history/evidence, Admin control, and Analyst/requester isolation.
- **Energy intelligence watch**, ID `0067ae6c-db97-4c98-a439-2935ec81f320`, is Buyer-owned, private, and enabled every 1,440 minutes. Its first scheduled run read the real stored **Brent crude — EIA monthly** series. Status PARTIAL, Price AVAILABLE and seven domains MISSING, observed risk UNKNOWN. First baseline does not generate a change alert. No enterprise demand/inventory/PO/lead-time observations were fabricated.
- The agent reads stored observations; automatic EIA refresh still requires the organization's provider key. Phase 4 alerts use in-app delivery. No email or external workflow was queued or sent during this implementation.

- Final preservation verification confirms all existing RFI/supplier/document/analysis records, users, chunks, configuration and 138 market observations are unchanged. The only existing-record change is the normal Phase 2 alert-rule `last_evaluated` timestamp. The backup was successfully restored into a temporary database to verify this difference; that database was removed. Environment file checksum and mode 0600 are unchanged; email/workflow queues remain empty.
- The second live agent evaluation completed PARTIAL with zero material changes and no duplicate alert. Next scheduled run after setup: **9 September 2026, 12:41 WIB**. PostgreSQL and application services remain active.
- Final tests also verify that shared RFI aggregates respect the underlying response permissions, and synchronous collection that exceeds the time budget cannot publish. Final totals are **90 PostgreSQL passed; 84 SQLite passed, six PostgreSQL-only tests skipped**.
