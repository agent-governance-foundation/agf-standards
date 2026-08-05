# Worked example: revocation race window (case-agf-synth-0001)

Rail-neutral push payment. Delegation chain A → B → C with attenuation at each
hop. Revocation becomes effective between the decision and the execution
attempt but is only observed by the runtime after the request has already
been dispatched. Payment settles; reconciliation opens an exception.

Every field named `_kind` in [`trace.json`](trace.json) tells you whether that
block is a real AGF schema shape (kernel `decision.schema.json` /
`receipt.schema.json` / `invalidation.schema.json`, Spec 02 delegation JWTs,
Spec 05/28 revocation semantics) or something invented for this worked
example (settlement, reconciliation — AGF has no native payment-rail concept,
so those two blocks are a synthetic wrapper around real AGF evidence, not AGF
output).

All identifiers are fictional (`acme` namespace, `example.com`-equivalent
DIDs); no production data appears in this repository, consistent with the
convention in [`schemas/kernel/fixtures/`](../../../schemas/kernel/fixtures/).

## Actors

| Role | DID |
|---|---|
| Root grantor (human) | `did:agf:acme:alice` |
| Agent A — payment-orchestrator | `did:agf:acme:agent:payment-orchestrator` |
| Agent B — payment-executor | `did:agf:acme:agent:payment-executor` |
| Agent C — payment-gateway-adapter | `did:agf:acme:agent:payment-gateway-adapter` |
| PDP | `did:agf:acme:pdp-01` |
| Execution gateway | `did:agf:acme:gateway-01` |

## Attenuation at each hop

- **Root → A**: scope `[initiate:payment, read:account-balance, read:vendor-directory]`
- **A → B**: scope narrowed to `[initiate:payment]` — A keeps the read
  scopes for itself, delegates only payment initiation onward.
- **B → C**: scope stays `[initiate:payment]` but gains constraints —
  `max_amount: 5000 USD`, `target_account_prefix: acct_vendor_`. Attenuation
  here is constraint-narrowing, not action-dropping.

Chain lineage is `hop2.parent == hop1.jti`, `hop1.parent == hop0.jti` — the
real AGF linkage mechanism (Spec 02), independent of the `case_id` label.

## Timeline

| Event | Field | Timestamp | Offset |
|---|---|---|---|
| Decision (ALLOW) | `decision_receipt.decided_at` | 2026-08-04T14:00:00Z | T+0s |
| Revocation issued & effective | `revocation_record.revocation_issued_at` / `effective_at` | 2026-08-04T14:00:01Z | T+1s |
| Execution attempted (request dispatched) | `execution_receipt.execution_attempted_at` | 2026-08-04T14:00:02Z | T+2s |
| Execution outcome known (accepted) | `execution_receipt.completed_at` | 2026-08-04T14:00:03Z | T+3s |
| Revocation observed by runtime | `revocation_record.revocation_observed_at` | 2026-08-04T14:00:33Z | T+33s |
| Payment settled | `settlement_record.states[1].at` | 2026-08-04T14:00:47Z | T+47s |
| Reconciliation exception opened | `reconciliation_exception.reconciliation_opened_at` | 2026-08-04T14:05:47Z | T+347s |

The deliberate edge case: `decided_at < revocation_effective_at <
execution_attempted_at < revocation_observed_at`. The decision was correct
when made — the chain was fully valid at `decided_at`. Authority ended one
second later. The gateway, unaware, dispatched the request a second after
that. The runtime didn't learn about the revocation until 31 seconds after
the request had already gone out. Nothing in the pipeline was wrong in
isolation; the composition produces a window where a signed ALLOW decision
and the authority it attests to have already diverged by the time it's
acted on.

## Correlation: real FK vs reconstructed

This is probably the sharper part of this worked example, so flagging it up
front rather than waiting for you to find it:

**Backed by an explicit reference field (provable by following a pointer):**
- `execution_receipt.decision_ref` → `decision_receipt.id`
- `settlement_record.execution_receipt_ref` → `execution_receipt.id`
- `reconciliation_exception.{settlement_ref, execution_receipt_ref, decision_ref}`
- `hop2.parent` → `hop1.jti`, `hop1.parent` → `hop0.jti`

**Not backed by a stored reference — reconstructed by matching values across
records:**
- `decision_receipt.authority_refs` contains `del_hop1_c204be`, and
  `revocation_record.subject` is also `del_hop1_c204be` — but there is no
  field on the decision artifact or the revocation record that points at
  the other. The link is an equality join on the delegation ID, done after
  the fact. In the reference runtime, this join happens implicitly at
  *validation* time (the chain hash is checked against the revocation
  index during `/v1/decide`), not as a persisted back-reference you could
  query independently of re-running that logic.
- `del_hop2_9e5b71` is invalidated by branch-cut (Spec 05 §3) as a
  descendant of the revoked `del_hop1_c204be`, but no record here says so
  explicitly — that inference requires walking `parent` links yourself.
- `revocation_issued_at == revocation_effective_at` is a property of this
  single-instance deployment's revocation model (Spec 28 §4.3: no
  propagation delay to the index), not something evidenced by two
  independent timestamps in the record — it's one timestamp used for both
  requested fields.

**Persistence history, since the first draft of this trace:** at the time
this was originally drafted, `effective_at`/`observed_at` (`occurred_at`/
`detected_at` in the kernel schema) was a real field in
`invalidation.schema.json` but **not actually persisted anywhere in the
reference runtime** — the two-timestamp gap existed only in the spec, not in
running code. That gap has since been closed: `detected_at` is now a real,
persisted field on every revocation record, for every backend. But closing
it surfaced a fact worth being precise about, because it changes which
backend this trace's own scenario is realistic for:

- For a live-Postgres-backed deployment (`postgres` or `postgres+notify`),
  `detected_at` is written in the *same transaction* as `revoked_at` — the
  decision path always does a live, synchronous read, with no cache in
  between. There is no lag to observe. `revocation_observed_at` in this
  trace being 32 seconds after `revocation_effective_at` is **not
  reproducible** under that backend — it would always be zero.
- The lag this trace depicts only occurs under a file/cached-revocation-
  list-backed deployment, where a node's local cache can genuinely be
  stale relative to the moment a revocation actually took effect. That's
  the deployment topology this scenario should be read as modeling — not
  the live-Postgres path.
- Separately, and this has *not* changed: `detected_at` records when
  *this evidence chain* first observed a revocation — it says nothing
  about whether authority was re-validated at the exact instant of
  execution. AGF performs exactly one authority check per decision,
  synchronously, with no re-check between `/v1/decide` returning and the
  gateway acting on it. Persisting `detected_at` closes the "when did we
  learn about this revocation" evidentiary gap; it does not touch the
  separate "was authority still valid at the instant of execution" gap
  this trace's core timeline is built around. Those remain two different
  claims — closing one didn't close the other.

**Missing entirely:**
- Nothing in the AGF-native artifacts (decision, execution receipt) records
  that a *disputed* revocation exists for this chain — that fact only shows
  up in the reconciliation exception, which is outside AGF's schema. If you
  only had the decision and execution receipt in hand, you could not tell
  the authority was later disputed; you'd need the revocation record and
  the reconciliation job's cross-check to surface it.

## Files

- [`trace.json`](trace.json) — full bundle, one file, all records under
  top-level keys matching this narrative's section names.
