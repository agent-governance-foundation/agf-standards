# Specification 28: Federation Revocation Sync

**Version:** 0.1.2 (Draft)
**Status:** Working Draft — §3-7 (the full single-instance mechanism: storage layer, both revocation write paths, decision-time integration, and audit surfacing split by audience) has a reference implementation. §8 (multi-deployment generalization) remains a protocol-only design, matching Spec 27's precedent, pending a second independent implementation to verify interoperability against.
**Supersedes:** None — extends Spec 26 §8's stated future direction and Spec 05's revocation model into the bilateral-federation case
**Layer:** Profile

## 1. Introduction

Spec 26 §8 names the gap this spec closes: cross-org revocation staleness is left at TTL-only staleness bound, because a receiving org holding only a Trust Summary has no revocation-table key to check, and cannot ask the issuing org synchronously without coupling every cross-org decision's latency and availability to a remote org. Spec 27 §5 sketches the same idea generalized to a standalone registry, but stays protocol-only because it requires infrastructure nobody operates.

This spec sits between those two: it defines revocation sync for the case Spec 26 already covers — two orgs with an **active bilateral federation trust relationship** — not the standalone-registry case Spec 27 describes. §3 establishes a deployment scenario that changes this mechanism's shape considerably from what "federation revocation sync" suggests at first read; §8 covers the case where that scenario doesn't hold.

## 2. Problem Statement

A Trust Summary (Spec 24) carries `chain_hash`, not the underlying chain's `jti`s — that compression is deliberate (Spec 26 §9: the raw chain is not routinely disclosed to the receiving org). The consequence: even though the receiving org's own decision logic already knows how to check revocation for chains it walked directly, it has no key to check revocation for a chain it only ever saw as a hash. A Trust Summary's own TTL is the only bound on how stale that blind spot can get — a chain revoked shortly after a summary is issued is still accepted as fully trustworthy for the remainder of that summary's TTL window.

This is a narrower, more precise restatement of "federation revocation sync" than the phrase suggests: it is not about two servers being unable to reach each other. It's about the receiving side of a Trust Summary never having been given the piece of data it would need to check revocation itself.

## 3. Deployment Scenario: Single-Instance Multi-Tenant

When multiple orgs with a bilateral federation trust relationship are tenants of the **same shared AGF deployment instance** — the scenario Spec 24 §4 and Spec 26 §3 already establish as the reference signing model — "federation" between them is two rows in one table, not two independently-operated servers. A signed, push-based mechanism between peers that are, in fact, the same process reading the same data store is not a network protocol problem; it is a same-transaction data-availability problem. §4-7 design for that scenario. §8 covers what changes when the two orgs are tenants of genuinely separate, independently-operated deployments instead.

## 4. Core Mechanism — Chain-Hash Revocation Index

### 4.1 Trigger

Both existing revocation operations (Spec 05 §3) — single-delegation revocation and branch-cut revocation — already produce the exact set of newly-revoked `jti`s as part of completing the revoke. This spec adds one step to that existing revoke path: cross-reference each newly-revoked `jti` against every previously-logged chain (Spec 26 §9's chain log, populated whenever a Trust Summary is built) whose tokens contain a JWT with that `jti`.

**Any one revoked `jti` within a logged chain is sufficient to mark its `chain_hash` revoked.** This is not a new rule invented here — Spec 02's chain validation already requires every hop to be currently valid for the chain as a whole to be valid, and a `chain_hash` is a hash over the entire chain (Spec 25), so a chain containing even one now-revoked link was never a chain that should still validate. This cross-reference does not distinguish which position in the chain the revoked `jti` occupies, or how many of the chain's `jti`s end up revoked over time — the first match is sufficient, and later matches against an already-revoked `chain_hash` are §4.2's no-op case.

### 4.2 Revocation Index Record

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `chain_hash` | string | Yes | The chain_hash (Spec 24 §3) this revocation applies to. Primary key — one entry per chain_hash. |
| `revoked_at` | number | Yes | When this chain_hash was marked revoked. |
| `reason_text` | string | No | Optional, implementation-defined explanatory string — the triggering revocation's own reason, preserved as given, no required shape. |
| `reason_category` | string | No | Optional classification for structured reporting. When present, MUST be one of Spec 05 §4.3's enum (`compromised`, `superseded`, `mission_complete`, `policy_change`, `behavioral_drift`). Implementations are not required to populate this field, and MUST NOT discard `reason_text` merely because a category could not be determined. |

An implementation MAY additionally store which `jti` triggered the entry for internal audit/dispute traceability, but MUST NOT expose it to any party querying this index — see §6.

Entries are append-only, same invariant as Spec 05 §8.5: a `chain_hash` that appears in this index stays revoked permanently. A second revocation event for the same `chain_hash` (e.g. two different `jti`s within the same chain are revoked separately) MUST be a no-op, not an error — the same "race condition: same delegation revoked twice" handling Spec 05 §8.5 already requires, applied one level up at the chain-hash granularity.

`chain_hash` itself is not defined by this spec — it is Spec 24 §3's field, computed per Spec 25's canonicalization over the full chain plus policy version. This index's `chain_hash` key inherits Spec 25's stability/collision-resistance property rather than asserting a separate one; this spec's only requirement is that equal inputs (Spec 25 §2) always produce the same key to index against, which Spec 25 already guarantees.

### 4.3 Atomicity and Propagation

**The index write MUST be atomic with the triggering revocation — same transaction, both commit or both roll back.** This is a correctness requirement, not a performance optimization: this index's entire purpose is closing a staleness gap, so an implementation where a delegation revocation commits successfully but its corresponding index write silently fails would reintroduce exactly the gap this spec exists to close, in a way that is harder to detect than the original TTL-only staleness — a revoked delegation would appear in every other system as revoked, while a Trust Summary built from its chain would continue validating. An implementation MUST perform §4.1's cross-reference and §4.2's index write inside the same transaction as the revocation write itself, and MUST fail the whole revocation request on any failure in that step, rather than committing the revocation while silently skipping the index update.

Performing this within the same transaction also means there is no propagation delay to design around: this is strictly stronger than Spec 05 §5.5's bounded-propagation-guarantee targets for the case this spec covers — propagation latency is zero by construction, because there is no second system to propagate to.

### 4.4 Index Lifecycle

No independent pruning policy — an index entry's lifecycle MUST be tied to its corresponding chain-log entry (§4.1): when the chain log's own retention policy (Spec 26 §9) removes a chain_hash entry, the corresponding revocation-index entry MUST be removed with it, since a removed chain-log entry means §7's proof-retrieval fallback and §4.1's cross-reference source are both already gone for that hash — there is nothing left for the revocation entry to protect. This is safe specifically because a Trust Summary's TTL is far shorter than any plausible chain-log retention window: by the time a chain-log entry is eligible for removal, every Trust Summary that could have referenced its `chain_hash` has already expired on TTL grounds regardless of revocation status (§5). Until removed, entries are permanent and immutable (§4.2) — there is no separate expiry or archival tier the way Spec 05 §4.4 defines for oversized revocation lists; this index is not expected to reach that scale, since it only grows in proportion to chains that were both summarized and later revoked, not every revocation in the system.

## 5. Decision-Time Integration

The Trust Summary verification path (Spec 26 §5) gains one additional check, alongside the existing signature/subject-org/federation-trust checks, before a summary is accepted: the presented `chain_hash` MUST be checked against the revocation index (§4.2). If present, the decision is denied with a distinct reasoning code (e.g. `chain_hash_revoked`) identifying this specific failure, using the same response shape every other Trust Summary verification failure already uses (Spec 26 §5).

This check supplements, not replaces, the existing TTL bound (§2) — a summary can still be rejected for being expired even if its chain was never revoked, and can now also be rejected for having a revoked chain even if it is still within its TTL window. The two checks are independent; either failing is sufficient to deny.

## 6. Audit Semantics and Privacy: Two Distinct Audiences

This spec's audit trail has two readers with deliberately different visibility, not one:

**The issuing org, on its own delegation's audit record** (the org whose delegation was originally revoked, viewing its own data): full detail. The existing revocation audit entry (Spec 05 §7.4) already records the triggering revocation's own delegation id, reason, and affected set; an implementation MAY add one field to that same, already-internal record — which `chain_hash`(es), if any, were found and marked revoked as a consequence (§4.1). This is the org's own forensic/dispute record about its own delegation; there is no privacy boundary to enforce against its own data.

**The receiving org, on the decision that got denied** (§5): minimal, by design. The `jti` that triggered a given index entry (§4.2) exists solely for the issuing-org-facing audit record above — it MUST NOT be surfaced in the decision response, any reasoning string, or any audit endpoint the receiving org can query. The receiving org's decision response MUST reveal only that the specific chain_hash it already possesses is now invalid — never which delegation within that chain was revoked, never `reason_text` or `reason_category` (§4.2), and never anything about the issuing org's internal delegation structure. This mirrors Spec 26 §9's existing principle: `chain_hash` itself is not a secret (the receiving org already has it, it travels inside every Trust Summary by design), but the chain it addresses is, and a revocation-index implementation MUST NOT become a side channel that leaks more about that chain to the receiving org than it already legitimately possesses.

An implementation MUST apply org-scoping to any audit endpoint surfacing revocation-index data — the same access-control principle Spec 26 §9 already requires for proof retrieval (ownership or active federation trust), not a new boundary invented here — since `reason_text`/`reason_category` alone, without the triggering `jti`, is still issuing-org-internal information about why a delegation was revoked, not something automatically owed to every org that happened to receive a Trust Summary built from it.

## 7. Interaction with Proof Retrieval (Spec 26 §9)

When a decision's risk score crosses the policy-driven proof-retrieval threshold, full-chain proof retrieval (Spec 26 §9) already re-validates the underlying chain — which independently re-derives revocation status via the normal same-org revocation check on those tokens' `jti`s. §5's revocation-index check is a fast, cheap short-circuit that catches the common case without needing the heavier full-chain proof fetch; proof retrieval remains the authoritative fallback for the high-risk case. The two are complementary: §5 answers "was this specific hash ever revoked," proof retrieval answers "is this chain currently, fully valid" — a strictly stronger question only worth asking when risk justifies the cost (Spec 26 §9's existing threshold).

## 8. Generalization to Independent Deployments

§3-7 require no network protocol because the revoking and verifying parties share a data store. When the two orgs are tenants of genuinely separate, independently-operated deployments instead — the scenario Spec 27 is written for — §4's same-transaction mechanism has no counterpart to run on: a revocation recorded on one deployment is invisible to the other by construction. At that point, the mechanism generalizes as follows, reusing the delivery model already established for other outbound event delivery in this protocol family (signed payload, retry with exponential backoff, fire-and-forget) rather than inventing new transport:

- **Targeted delivery, not broadcast:** a federation revocation event is delivered to the specific peer deployment resolved from the federation-trust relationship's registered counterpart endpoint — a registry extension not designed further here, out of scope until a second independent deployment exists to specify it against.
- **Signed payload:** `{chain_hash, revoked_at, reason_text, reason_category}` — deliberately excludes the triggering `jti` (§6) even across deployments, signed with the revoking deployment's own signing key, verified by the receiving deployment via the same trust-anchor resolution Spec 26 §3 already defines for Trust Summaries.
- **Replay protection:** each event carries a monotonically increasing per-`chain_hash` sequence number, not a timestamp alone — clock skew between independent deployments is a real concern chain validation already accounts for elsewhere in this protocol family, and revocation events should not reinvent a weaker version of that. A receiving deployment MUST reject an event whose sequence number is not strictly greater than the last one it applied for that `chain_hash`.
- **Conflict handling:** identical to §4.2's append-only, no-op-on-duplicate model — a `chain_hash` revoked via two independent paths converges to the same state regardless of delivery order, the same invariant Spec 05 §8.5 already establishes.
- **Offline peers:** identical retry/backoff behavior to any other best-effort event delivery in this protocol family; beyond the retry budget, falls back to the existing TTL bound (§2) exactly as it does today. An unreachable peer does not get a stronger guarantee than "the summary expires eventually" — Spec 26 §8 already establishes that cross-org decision latency must not depend on a remote org's availability, and this generalization does not reverse that requirement.

This section is specified now, alongside the part meant to be implemented immediately, so the single-instance mechanism (§4-7) is demonstrably not a dead end requiring a redesign if a second independent deployment appears — but it remains a protocol-only design, for the same reason Spec 27 stays protocol-only: there is no second deployment yet to verify interoperability against.

## 9. Non-Goals

- No synchronous cross-org network call at decide-time — §2's stated constraint remains satisfied throughout: trivially in §4-7 (no cross-org call exists), and by design in §8 (push, not pull, exactly as Spec 26 §8 already establishes).
- No disclosure of the revoked chain's contents, issuing org's delegation structure, or the triggering `jti` to the receiving org (§6).
- No change to the existing TTL bound's role as the outer staleness ceiling — this spec adds a second, independent check, not a replacement.
- Does not address Spec 27's standalone-registry case — an org with no bilateral federation trust relationship to the issuer remains out of scope for this spec entirely, exactly as it already is for Spec 26.

## 10. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-17 | Initial public working draft |
| 0.1.1 | 2026-07-17 | Normative tightening: explicit any-jti-sufficient rule (§4.1), chain_hash stability inherited from Spec 25 (§4.2), atomicity upgraded to a MUST requirement with rationale (§4.3), index lifecycle tied to chain-log retention (§4.4), and audit semantics split into issuing-org (full detail) vs. receiving-org (minimal) visibility with an explicit org-scoping requirement (§6) |
| 0.1.2 | 2026-07-17 | §4.2's single required `reason` field (an enum) replaced with `reason_text` (optional, implementation-defined explanatory string) plus a separate, optional `reason_category` classification validated against the enum only when present — preserves the original explanation's fidelity without requiring conformance to a fixed taxonomy, while leaving room for standardized classification later. §6 and §8's signed-payload description updated to match. |
| — | 2026-07-17 | A reference implementation of §3-7 now exists (no further normative content changed, so no version bump). |
