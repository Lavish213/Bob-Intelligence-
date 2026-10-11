# Bob Intelligence

Bob is the pre-call evidence and planning worker for REI-AGENT. It builds an advisory call brief from shared Supabase `leads`, `properties`, and `intel_packets`. It does not speak, calculate offers, grant permissions, or authorize outbound calls.

The October 2026 repair replaces disconnected tables and unreliable event scheduling with a versioned contract and database-owned jobs. Sophia's matching repair validates the brief, includes useful guidance in the model context, and sends timestamped checklist facts back through `bob_record_call_facts`.

## Run and verify

Requires Python 3.11 or 3.12, uv 0.12.23, and Node 20 for embedded database tests.

```sh
uv sync --locked
uv run pytest --cov=backend --cov-branch -q
uv run ruff check backend tests/test_bob.py
npm ci --prefix tests --ignore-scripts --no-audit --no-fund
npm run test:database --prefix tests
```

Configure an untracked `.env` from `.env.example`. The worker refuses placeholder service keys and invalid limits. `uv run python -m backend.main --once` processes one bounded batch; `uv run python -m backend.main` runs until SIGTERM/SIGINT. It stops claiming new work on shutdown and lets the bounded current operation finish.

## Coordinated staging rollout

1. Keep outbound calls disabled. Confirm both services use the same Supabase project and tenant.
2. Supply the existing REI database baseline and its tenant/suppression migrations. Bob's migration requires `leads(id, tenant_id, property_id, stage, opted_out, dnc_blocked, updated_at)`, `properties(id, tenant_id, distress_score)`, and `intel_packets(lead_id, tenant_id)`. Both repositories still lack a complete baseline for all REI tables. Duplicate intelligence rows must be reviewed before the unique index can apply.
3. Apply `supabase/migrations/20261011_bob_durable_briefs.sql` once, from this repository, in staging. It adds brief/checklist columns, job leases, decision history, event outbox and restricted RPCs. Do not apply a copied migration through a second independent deployment system.
4. Deploy the matching REI brief consumer and feedback bridge from its repair branch. Legacy/unversioned, malformed, expired and wrong-lead briefs are ignored in favor of the normal call policy.
5. Start Bob with the service role and `BOB_TENANT_ID`. Verify claim/commit/fact-feedback transactions and lease recovery against actual Supabase before enabling production.
6. Leave `KARPATHYS_URL` empty until the receiving service proves the contract. Optional delivery uses HTTPS, `/api/ingest/bob/brief-created`, `X-Karpathys-Secret` from `KARPATHYS_WEBHOOK_SECRET`, and `Idempotency-Key`. The receiver must independently authorize, deduplicate and validate events. A successful HTTP status establishes acceptance, not completed downstream work.
7. Record controlled real calls and validate permissions, suppression, callbacks and booking. Bob never emits an automatic `lead-ready` instruction and all dialing still requires REI preflight.

## Operating the worker

Brief, decision and event are committed in one transaction. Each job has a generation token and a bounded lease. Source changes invalidate a pending result. Failures back off and quarantine after five failed jobs; events back off and become dead letters after ten failed deliveries. Failed HTTP or DB acknowledgment never counts as accepted delivery.

Operators should monitor tenant-filtered `bob_brief_jobs` (quarantined/failures/lease expiry), `bob_decisions`, and `bob_outbox` (pending/dead/oldest age). Review the cause before clearing quarantine. Do not blanket-reset other tenants' work. Establish retention, backups, dead-letter alerts and worker heartbeat alerts in production; those operational integrations are not supplied by this code.

The event transport is at least once. A response can be lost after a receiver commits; retries keep the same event ID. Receiver deduplication is therefore required. External delivery may be disabled while Bob still writes the shared brief and retains a local event record.

Audit, grades, all findings and local test limits: [BOB-AUDIT.md](docs/BOB-AUDIT.md), [finding ledger](docs/BOB-FINDINGS.json).
