# Specification 26: Trust Relay Protocol (AGF-TRP-1.0)

**Version:** 0.2.0 (Draft)
**Status:** Working Draft  
**Supersedes:** 0.1.0  
**Layer:** Profile  

## 1. Introduction

Specs 24 and 25 define the Trust Summary artifact and its canonical serialization. This spec defines the protocol around it: how a summary actually moves from the org that issued it to the org that decides against it, what gates a summary is subject to besides its own signature, and what happens after a decision is made. This is Spec 03's Global zone (§2.3), realized as an extension of the existing bilateral federation mechanism rather than a standalone consortium-operated registry — see Spec 27 for why that split was chosen and what remains protocol-only.

## 2. Prerequisite: Bilateral Federation Trust

A Trust Summary does not, by itself, authorize anything. Before org B will accept a summary issued by org A, an **active** federation trust relationship must exist between the two orgs — the same invite/accept bilateral peering mechanism that predates this protocol (`POST /v1/federation/invite` → `POST /v1/federation/{id}/accept`). Trust Summaries ride on top of that relationship; they do not replace it or substitute for it. An org with no federation peering to the issuer is denied with `no_active_federation_trust`, identical to the pre-existing raw-chain cross-org path this protocol runs alongside (§5).

### 2.1 Establishing the Peering

These rules apply to both cross-organisation paths: a raw chain whose root token's issuer is owned by another organisation (item 3, §5), and a Trust Summary. They build on the core issuer rules: every token's verifying key belongs to its issuer (Spec 02 §3.4), and every issuer is trusted for the requesting organisation (Spec 02 §3.10, Spec 08 §3.4).

1. **Active peering.** A decision on a chain or Trust Summary from another organisation requires an **active** peering. A peering that is not active MUST be denied (`no_active_federation_trust`) independently of any federation selection (Spec 06 §6.8), before any selection is read.
2. **Failure never becomes a same-organisation decision.** If the PDP cannot establish any of the following, the decision MUST be DENY:
   - which organisation owns the root token's issuer;
   - the peering it requires;
   - the requesting organisation's own registry entry.

   The PDP MUST NOT continue as if the request were same-organisation. It records which of these causes occurred, with distinct reasons:
   - **Malformed input** (`federation_chain_malformed`): a token cannot be decoded, or its issuer is missing or not a string.
   - **Lookup failure** (`federation_precheck_unavailable`): the organisation registry or the peering could not be read.
   - **Identity failures**: as Spec 02 §3.10 (`identity_not_found`, `identity_unavailable`).

   On the Trust Summary path, a lookup failure is `trust_summary_precheck_error`, and a malformed summary fails verification (`trust_summary_verification:<REASON>`).
3. **Classification by owner (raw chain).** The root token's issuer is classified by the organisation that **owns its identity** (Spec 08 §3.4), never by the identifier's text.
   - **Owned by the requesting organisation:** a same-organisation decision. Every token's issuer MUST be owned by the requesting organisation (Spec 02 §3.10).
   - **Owned by another organisation:** a cross-organisation decision under this section. The first applicable reason denies it:
     1. `caller_org_not_registered`: the requesting organisation has no organisation-registry entry. The PDP MUST NOT register it implicitly.
     2. `issuer_org_not_in_registry`: the owning organisation is unknown or inactive in the registry.
     3. `no_active_federation_trust`: no active peering exists (item 1).

     Otherwise, every token's issuer MUST be owned by the requesting organisation or by that peer organisation. Any other issuer is denied (`issuer_not_trusted`), including an issuer owned by an organisation with which the requesting organisation has its own active peering. The root's peer is the chain's only permitted peer, and only its peering can supply a federation selection (Spec 06 §6.8).
   - **The PDP's platform identity:** the root is trusted only as Spec 02 §3.10 allows: its subject is owned by the requesting organisation. Platform signing does not establish trust for any other organisation. Platform-mediated federation beyond this is out of scope, and requires its own specification.
4. A federation selection that cannot be read is not a check failure under item 2. It is a policy-leg failure (Spec 06 §6.8), recorded per Spec 07 §3.3.

### 2.2 Federation Policy Selection

A policy the receiving organisation configured for this peering is a federation selection (Spec 06 §6.8). It is evaluated in addition to that organisation's mandatory policy, deny-overrides, on both the raw-chain and Trust Summary paths. Each organisation has its own selection for the peering. A peering does not carry a policy shared by both organisations.

### 2.3 Peering Lifecycle

1. **Identifiers are never reused.** A new peering between the same two organisations has a new trust identifier, so its federation slots start "not configured" (Spec 06 §6.8).
2. **Locks and order.** Two locks coordinate a peering's state with its federation slots:
   - the **peering lock**, one per trust identifier;
   - the **selection lock** of each organisation (the mutual exclusion of Spec 06 §6.6.4).

   Every operation that needs both takes the peering lock **first**, then the selection lock, and holds both **until its transaction commits or aborts**. A peering's state MUST be read under its peering lock, never from an earlier snapshot.

   | Operation | Locks, in order | In the same transaction |
   |---|---|---|
   | Deactivation | peering | Set the non-active state; write the deactivation record and the cleanup obligations (item 3) |
   | Reactivation | peering | Refuse unless every cleanup obligation is confirmed (item 7); set the active state |
   | Administrator change to a federation slot | peering, then the organisation's selection lock | Refuse a change that would select a revision unless the peering is active; otherwise apply the compare-and-set |
   | Cleanup prepare or execute (items 4–5) | peering, then the organisation's selection lock | As in items 4–5 |
   | Any other selection change | the organisation's selection lock only | Unchanged (Spec 06 §6.6.4) |

   Because a federation-slot writer holds the peering lock from its state check through commit, deactivation cannot commit between that check and the writer's commit. A writer that starts after deactivation reads the non-active state and is refused. No operation takes the selection lock and then the peering lock.

   **Across workers.** These locks MUST serialize every PDP worker, process and node that can change a peering's state or its federation slots: in the prescribed order, held through commit or abort.
   - A lock held by one MUST exclude all the others until its holder's transaction ends.
   - A lock that is local to one process or worker does not satisfy this.
   - The mechanism is left to the implementation, provided it has these properties; for example, database row locks or transaction-scoped advisory locks taken in the same database transaction.
3. **Deactivation commits first.** When a peering leaves the active state (revoked, or any other non-active state), one transaction commits:
   - the non-active state;
   - a deactivation record: the peering, the previous and new states, the principal and the time;
   - one **cleanup obligation** per organisation of the peering, naming the slot `federation:<trust identifier>`.

   No selection slot is written in this transaction. Deactivation does not depend on cleanup, and no cleanup-specific failure can leave the peering active. From the moment it commits, decisions under the peering are denied (§2.1 item 1).
4. **Cleanup request (prepare).** For an unconfirmed obligation with no open request, the PDP, under both locks:
   - reads the slot;
   - in the same transaction, **persists a cleanup request** containing:
     - the obligation;
     - the slot;
     - the operation `peering_deactivated`;
     - the expected version (the version just read);
     - the target "not configured";
     - an operation identifier.

     The identifier is derived from the organisation, the trust identifier, the deactivation record, the slot and the request's sequence number (Spec 06 §6.6.4 item 6).
   - If the slot is **already "not configured"**, the same transaction instead records the request with outcome `already_clear` and confirms the obligation, recording the slot's observed state:
     - **Never configured** (the organisation has no such slot): the state `never_configured`, with **no** version and **no** clearing operation. None exists, and none is invented.
     - **Cleared earlier:** the slot's version, and the operation identifier of the recorded change that left it "not configured".

     The obligation's evidence then names the cleanup request, and either the slot's initial state or the change that actually cleared it.
5. **Cleanup execution.** Under both locks, the PDP applies the persisted request exactly: the same operation identifier and the same expected version.
   - On success, in the same transaction, it records the change (Spec 06 §6.6.4 item 3) and confirms the obligation with the resulting version.
   - If the slot's version no longer equals the persisted expected version, the PDP **first** looks up the request's operation identifier in the recorded changes, under the selection lock (item 6). That covers the case where the request itself committed earlier with an uncertain outcome.
     - **Found:** its outcome is adopted.
     - **Lookup completed and found no recorded change:** the request is recorded as `superseded`, with the version observed. The next attempt is a **new** request (a new sequence number, so a new operation identifier) prepared under item 4.
     - **Lookup failed or uncertain:** nothing is recorded and no new request is prepared. The same request is retried later.

     Uncertainty alone never permits a new operation identifier, and a persisted request is never re-sent with a different expected version.
6. **Uncertain outcomes and restarts.** If an execution's outcome is uncertain (for example, the connection is lost at commit), or the PDP restarts with a request open, the PDP MUST NOT re-prepare. It first looks up the recorded change by the request's operation identifier, under the selection lock (Spec 06 §6.6.4 item 4):
   - If found, it adopts the recorded outcome. The obligation was confirmed in the same transaction.
   - If not found, it replays the same persisted request.

   Unconfirmed obligations MUST be retried until confirmed. The PDP SHOULD back off between attempts, and MUST log and count obligations unconfirmed beyond a configurable period.
7. **Reactivation.** A PDP that allows a peering to return to the active state under the same identifier MUST refuse the reactivation while any of its cleanup obligations is unconfirmed (item 2: the check is made under the peering lock, in the reactivation's transaction). A reactivated peering's slots are therefore "not configured". A selection is restored only by a new administrator change after reactivation. Reactivation MUST NOT restore, copy or re-point a selection by itself.
8. **Suspension of policy writes.** The cleanup of items 4–6 is exempt from any suspension of policy writes. The exemption is scoped narrowly:
   - it applies only to clearing a slot to "not configured";
   - only for a peering that is not active;
   - only to the PDP's own cleanup of a recorded obligation.

   Every other change to a federation slot remains subject to suspension. The clear cannot change any decision, because a peering that is not active is already denied (§2.1 item 1).

### 2.4 Transition from a Shared Peering Policy

Earlier versions of this specification applied one policy setting per peering, shared by both organisations, in place of the mandatory policy. A PDP retiring that setting:

1. MUST NOT remove an existing setting until it has a recorded resolution. A resolution is one of:
   - adoption into the federation slot of the organisation that owns the selected policy, as an immutable revision of that organisation's policy (a recorded Spec 06 §6.6.4 change made by that organisation's administrator);
   - an explicit, recorded decision by that organisation's administrator to retire the setting.

   Notice to administrators is not a resolution.
2. MUST NOT complete the transition while any setting is unresolved.
3. MAY, when a check made at the transition finds no existing setting, complete the transition by asserting that none exists. It MUST then refuse to complete if any setting is found.
4. MUST NOT migrate a setting into any organisation other than the one that owns the selected policy.
5. **Implements no shared-setting behaviour.** A PDP conforming to this version MUST NOT evaluate a shared peering setting in any form: not in place of a mandatory policy, not by removing one, and not during the transition. The transition is a precondition of putting such a PDP into service, not a mode of operation. Until it is complete, the earlier behaviour remains a property of the earlier implementation only.

## 3. Trust Anchor Resolution

**When multiple orgs are tenants of a single shared AGF deployment instance, resolving "the issuer's signing key" means resolving that deployment's shared platform key, not each tenant org's own individually registered public key.** This follows directly from Spec 24 §4's signing model: every Trust Summary produced by a single-instance deployment is signed with that deployment's platform key regardless of which tenant org called `/summarize`, so verifying against a tenant's self-registered key would only succeed by coincidence — where a tenant happened to register the platform's own key as its own, which no real, independently-operated org would do.

For a genuinely separate, independently-operated AGF deployment presenting a summary it signed with its own key, the verifier MUST resolve that key via the federation-registry path, with a TTL-cached lookup (default 3600 seconds). Same-deployment tenants never exercise this path — verification for them always resolves the shared platform key directly.

## 4. Zone Trust Decay

Spec 03 §3.3 describes trust adjustments as a decision crosses zone boundaries. This protocol applies exactly one such adjustment for the `domain_to_global` transition: a fixed −10, applied once, after the existing reputation-penalty step and before risk combination, clamped to `[0, 100]`. The other two transitions §3.3 describes (`local_to_domain`, `global_to_domain`) are Zone 1 (SDK-local-cache) concerns, not part of this cross-org relay, and are not separate numeric adjustments here — Zone 1's local cache either serves an unmodified prior decision or runs the offline risk-penalty table (Spec 03 §4.1), neither of which is a "trust decay" step distinct from what's described here.

## 5. `/v1/decide` Integration

`POST /v1/decide` accepts a `trust_summary` object as an alternative to `chain` — the two are mutually exclusive per request (enforced by a request-model validator). This is additive: the pre-existing raw-chain cross-org path (a `chain` whose root token's issuer is owned by a different org (§2.1 item 3), gated by the same federation-trust check) continues to work as before, under the rules of §2.1 and §2.2. When `trust_summary` is present:

1. The caller's own org identity is resolved server-side from their authenticated session (never from any field inside the submitted summary).
2. The issuer org is resolved from the registry; an active federation trust to the caller's org is required (§2).
3. The summary is verified (Spec 24 §5) against the resolved trust anchor (§3).
4. On success, the decision proceeds using the summary's `delegation_trust_score` (post zone-decay, §4) and `effective_scope` as inputs — `validate_chain()`/chain revocation are **not** re-run, since there is no raw chain in this path to walk; that verification already happened at the issuing org when the summary was built. Risk is computed fresh from the caller's own action/resource/context and policy, per Spec 24 §2.
5. On failure at any step, the request is denied via the same `DecideResponse` shape every other pre-check denial in this endpoint uses (HTTP 200, `decision: "DENY"`, a `reasoning` entry identifying the specific failure — `trust_summary_verification:<REASON>` for a verification failure, or the federation-trust reasons in §2).

## 6. Common Implementation Pitfalls

Documented here since they reflect real properties of the protocol worth any future implementer knowing about:

- **Subject-binding self-comparison.** A naive implementation of the `subject_org` check (Spec 24 §5) can compare the field inside the presented summary against itself, rather than against the presenting org's own server-resolved identity — a tautology that always passes, for any summary, for any presenting org. Implementations MUST derive "who is asking" from the presenting party's own server-resolved identity, never from a field inside the artifact being verified — this principle applies at every call site that checks subject binding, including Spec 27's design.
- **Signing-key/trust-anchor mismatch.** See §3 — an implementation that resolves the issuer's self-registered public key instead of the actual signing key used for same-deployment tenants will only work by coincidence, and will fail `BAD_SIGNATURE` for any two genuinely independently-keyed orgs. Verify the signing model against Spec 24 §4 directly rather than relying on passing tests alone.
- **Cross-org data exposure in proof retrieval** (§9). `chain_hash` is not a secret — it travels inside every Trust Summary by design — so the underlying chain-log lookup it addresses MUST be access-controlled independently. Treating a valid `chain_hash` alone as sufficient authorization for retrieval creates a cross-org data exposure.

## 7. Publication Ordering

Specs 24, 25, 26, and 27 are designed and published together as a single interoperable set — the signing-key model (§3), subject-binding requirements (§6), and the depth-vs-transmission-compression distinction (Spec 24 §1) are cross-referenced and mutually consistent across all four specs.

## 8. Revocation Propagation (Domain Zone, Spec 03 §4.2)

Separate from Trust Summary relay, but part of the same requirement set: revocation propagation latency within a domain SHOULD be measured and alerted on, not silently unmonitored, for revocation backends that support a real push event to measure against (see Spec 05 for backend options). An implementation using a push-based revocation backend SHOULD log an alert and expose a metric when propagation latency past a revocation event exceeds a configurable target (default 60s, per Spec 03 §4.2). This is **measurement and alerting, not enforcement** — a slow propagation is logged, not prevented or retried. Backends using a flat cache-based staleness window instead of push events are out of scope for this target; that is a different, already-documented tradeoff (Spec 05). For push-based backends, a conformant implementation reading its authoritative store live on every decision has no staleness window to enforce against — the metric exists for operational visibility, not because a correctness gap remains.

**Cross-org revocation staleness** was TTL-only as of this spec's original writing; it is now addressed by Spec 28, which defines a revocation-indexing mechanism for the bilateral-federation case. See Spec 28 for the mechanism; Spec 27 §5 remains the forward-looking sketch for a genuinely multi-deployment registry.

## 9. Policy-Driven Proof Retrieval

A Trust Summary is normally sufficient. Full-chain proof is retrievable on demand — not routinely — via `GET /v1/delegations/proof/{chain_hash}`, or automatically when a decision's own risk score meets a configurable threshold (default 70). Retrieval always revalidates the fetched chain through the normal Spec 02 path before returning it; stored data is never trusted as pre-verified.

**Access control**: the calling org must either own the chain-log record (it was the org that originally summarized this chain) or hold an active federation trust with the owning org — the same relationship model as §2, not a simple ownership-only check, since the entire point of proof retrieval is letting the *recipient* of a summary — not just its issuer — pull the underlying evidence. `chain_hash` is not a secret (§6); the access-control boundary has to be enforced explicitly rather than relying on the hash being hard to guess.

## 10. Discovery Metadata

`GET /v1/delegations/protocol-info` — unauthenticated, returns the protocol versions this deployment supports (`AGF-TS-1.0`, `AGF-C14N-1.0`, and the configured summary TTL). Deliberately minimal: this lets an integration partner or another implementation probe compatibility before attempting a relay, without implementing anything resembling Spec 27's full registry-discovery protocol.

## 11. Non-Goals

- No synchronous cross-org revocation check (§8).
- No per-org private key custody (Spec 24 §4) — a deliberate protocol choice, not an oversight.
- No standalone global registry (Spec 27) — trust anchor resolution in this version is either the local platform key or the existing bilateral federation-trust mechanism, never a third-party-operated service.

## 12. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
| 0.2.0 | 2026-10-08 | Draft: §2 extended. §2.1 Establishing the Peering: an active peering is required; failures never become same-organisation decisions (`federation_chain_malformed`, `federation_precheck_unavailable`); classification by the owner of the root issuer with ordered checks; one permitted peer per chain. §2.2 a per-organisation federation selection replaces the shared `policy_id` override. §2.3 Peering Lifecycle: peering and selection locks in a fixed order, held through commit, across every worker; deactivation commits first with cleanup obligations; persisted cleanup requests (`already_clear` including `never_configured`); recovery before supersession; reactivation refused until obligations are confirmed; narrow exemption from suspension of policy writes. §2.4 Transition from a Shared Peering Policy. §5 the raw-chain path runs under §2.1 |
