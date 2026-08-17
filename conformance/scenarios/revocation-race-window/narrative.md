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

### Depth validation

Per Spec 02 §3.6/§6, validity requires `len(chain)-1 <= min(max_depth
across all tokens)`. This chain has 3 tokens (`len-1 == 2`), so every token
must carry `max_depth >= 2`. `max_depth` is a static ceiling checked
against the chain's actual depth-from-root — it is not a decrementing
remaining-hops counter. The chain's values are `(3, 2, 2)`; hop1's
attenuation is carried by `scope`/`constraints` narrowing, not by reducing
`max_depth`.

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
the request had already gone out. The scenario intentionally composes
individually defined behaviors to expose a window where an ALLOW decision
artifact and the authority it represents have diverged by the time it is
acted on.

Spec 05 §5.5 governs a new decision evaluation during/after the propagation
window; this scenario models the dispatch of an already-issued decision
without a second authority evaluation. This is a scenario about the gap
between decision-time and execution-time authority, not a claim that AGF
permits dispatch after revocation. See "Correlation: real FK vs
reconstructed" below for the reference-implementation citation backing the
"no second authority evaluation" claim, and its caveat: that's verified
runtime behavior, not yet adopted normative spec text.

"ALLOW decision artifact" above describes artifact *structure*
(`decision.schema.json` shape), not a cryptographic guarantee — this
synthetic trace omits real signatures throughout (see `signature_status:
"omitted_synthetic"` on `decision_receipt` and the placeholder `signature`
on `execution_receipt`).

## Correlation: real FK vs reconstructed

This is probably the sharper part of this worked example, so flagging it up
front rather than waiting for you to find it:

**Backed by an explicit reference field (provable by following a pointer):**
- `execution_receipt.decision_ref` → `decision_receipt.id`
- `settlement_record.execution_receipt_ref` → `execution_receipt.id`
- `reconciliation_exception.{settlement_ref, execution_receipt_ref, decision_ref}`
- `hop2.parent` → `hop1.jti`, `hop1.parent` → `hop0.jti`
- `execution_receipt.upstream_event_ref` = `settlement_record.upstream_event_ref` —
  an explicit shared pointer tying execution acceptance to settlement's first
  `states[0]` entry as the same upstream event. Synthetic and non-native (this
  worked example's own convention, not an AGF or Spec 07 field), but an
  explicit stored match now, not same-second-timing inference.

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
running code. That gap has since been closed: `detected_at` is now
persisted by the implementation and represented in the decision evidence.
But closing it surfaced a fact worth being precise about, because it changes which
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
  This "exactly one check, no re-check" claim is verified against the
  current `agf-runtime` reference implementation, not merely asserted:
  `perform_decision()` (`src/presentation/api/routes/decide.py:115`) is
  called exactly once per request by `/v1/decide` (`decide.py:996`) and by
  each of the three gateway-proxy routes (`http_gateway_proxy.py:141`,
  `mcp_gateway_proxy.py:123`, `a2a_gateway_proxy.py:151`) — no second or
  independent revalidation call exists anywhere in that codebase as of this
  writing. That said, this is reference-implementation behavior, not
  normative specification text: no AGF spec currently states single-check
  decision semantics as a requirement. A draft RFC,
  `0000-single-check-decision-semantics` (`agf-standards/rfcs/`, status
  **Draft**), proposes formalizing exactly this — until it's adopted, two
  conformant implementations could in principle diverge on this point while
  both remaining spec-silent-compliant.

**Missing entirely:**
- Nothing in the AGF-native artifacts (decision, execution receipt) records
  that a *disputed* revocation exists for this chain — that fact only shows
  up in the reconciliation exception, which is outside AGF's schema. If you
  only had the decision and execution receipt in hand, you could not tell
  the authority was later disputed; you'd need the revocation record and
  the reconciliation job's cross-check to surface it.
- This example is intentionally terminal at exception-opening
  (`reconciliation_exception.state == "open"`, `closed_at: null`).
  SLA/ownership/closure lifecycle is out of scope — this scenario is about
  the revocation race window, not reconciliation process design.
- Who is authorized to revoke `del_hop1_c204be` — the specs (Spec 02, Spec 05
  §4.3, Spec 00 §3.6) require a `revoked_by`/`actor` DID on a revocation but
  do not currently define whose DID may legitimately hold that role. A draft
  RFC, `0000-revocation-authorization` (`agf-standards/rfcs/`, status
  **Draft**), proposes a grantor-or-ancestor rule under which `alice` — the
  chain's root grantor, not `del_hop1_c204be`'s direct issuer — would qualify
  as an authorized ancestor; a candidate `agf-runtime` enforcement of that
  proposed rule exists (`RR-0002`,
  `agf-profile/implementation/review-records/`, status **Pending**). Neither
  is adopted, so `revocation_record.actor` in this trace is not currently
  backed by any settled specification rule — this is cited as the relevant
  in-flight work, not as evidence the gap is closed.
- What canonicalization/hashing rule governs `constraints.max_amount`,
  `target_account_prefix`, and `policy.hash` reproducibility — no RFC
  currently addresses this (unlike the two gaps above, which at least have
  Draft proposals); `trace.json`'s `policy.note` continues to label this
  illustrative-only rather than implying a rule exists.

## Execution-Time Authorization Validation (Spec 30) — the corrected behavior, now the default

This scenario's central finding — an already-issued `ALLOW` can be dispatched
after its authority is revoked, because AGF performs exactly one check, at
decision time — is now addressed by
[Spec 30](../../../specs/30-execution-time-authorization-validation.md)
(`RFC 0000-execution-time-authorization-validation`): a gate a PEP performs
immediately before dispatch, re-checking only what can actually change in
that window (revocation, expiry, platform emergency-halt state) — never
signatures, chain structure, scope, or policy, none of which can change on an
already-verified chain.

`trace.json`'s `execution_validation_check` block shows exactly what this
control produces for this scenario's own chain and timeline: a check at
`checked_at: 1785852002` (the same instant as
`execution_receipt.execution_attempted_at`) finding `del_hop1_c204be` revoked,
`result: "invalid"`, and dispatch blocked before `upstream_status: accepted`
ever happens. No settlement, no reconciliation exception; there is nothing
left to reconcile.

**This is no longer just what the control would have caught — it is current
default behavior.** `RR-0003` (`agf-profile/implementation/review-records/`)
was **Approved on 2026-08-15**, flipping `execution_time_validation_enabled`
to `True` as `agf-runtime`'s shipped default: the built-in HTTP/MCP/A2A
gateway proxies now perform this check before every dispatch unless a
deployment explicitly opts out. **This trace's own recorded outcome — decision,
dispatch, settlement, reconciliation exception — reflects the pre-RR-0003
state this scenario was built to demonstrate, preserved here as the historical
account of the gap that motivated Spec 30.** A fresh occurrence of this exact
scenario against a current, default-configured deployment would instead follow
`execution_validation_check`'s outcome: blocked at dispatch, nothing to settle
or reconcile.

One boundary stays explicit and is not resolved by this default flip: the
interval between the execution-time check itself and the instant of dispatch
is not atomic and is not claimed to be closed (Spec 30 §7/§8.1) — a
third-party upstream cannot participate in AGF's own transaction, so this is
a narrowed, auditable residual window, not an eliminated one.

The API path
(`POST /v1/decisions/{artifact_id}/validate-execution`, Spec 30 §5) is
unaffected by that default either way — it's always available for a PEP to
call explicitly, independent of whether the built-in gateway proxies
auto-invoke it.

## Payload identity (`request_hash`)

`decision_receipt.action.request_hash`, `execution_receipt.request_hash`,
`settlement_record.request_hash`, and `reconciliation_exception.request_hash`
all carry the same value:
`cad95970d2b07741ebdcf00d06a002854b19154406e387cad061ab23de460a64`. Unlike
`request_ref` (a bare correlation string), this is an actual SHA-256 digest,
computed over this worked example's own canonical JSON encoding of the
payload fields that matter for identity — `action_target`, `amount`,
`from_account`, `scope`, `to_account` — with object keys sorted and no
whitespace:

```
{"action_target":"payments/acct_vendor_4471/push","amount":{"currency":"USD","value":4200.0},"from_account":"acct_org_treasury_001","scope":["initiate:payment"],"to_account":"acct_vendor_4471"}
```

A reviewer can recompute this independently (e.g. Python:
`hashlib.sha256(canonical_bytes.encode()).hexdigest()`) and confirm all four
records agree — that agreement is what establishes, rather than merely
asserts, that the decision, the execution, the settlement, and the
reconciliation cross-check all describe the *same* payload. This is this
worked example's own illustrative convention, not an AGF-specified hashing
method, field set, or canonicalization rule — no AGF spec currently defines
one (see `policy.hash`'s note in `trace.json`, which is the same kind of
illustrative-only field for a different reason).

## Files

- [`trace.json`](trace.json) — full bundle, one file, all records under
  top-level keys matching this narrative's section names.
