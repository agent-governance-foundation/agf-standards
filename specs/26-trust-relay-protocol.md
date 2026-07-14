# Specification 26: Trust Relay Protocol (AGF-TRP-1.0)

**Version:** 0.1.0 (Draft)
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Profile  

## 1. Introduction

Specs 24 and 25 define the Trust Summary artifact and its canonical serialization. This spec defines the protocol around it: how a summary actually moves from the org that issued it to the org that decides against it, what gates a summary is subject to besides its own signature, and what happens after a decision is made. This is Spec 03's Global zone (§2.3), realized as an extension of the existing bilateral federation mechanism rather than a standalone consortium-operated registry — see Spec 27 for why that split was chosen and what remains protocol-only.

## 2. Prerequisite: Bilateral Federation Trust

A Trust Summary does not, by itself, authorize anything. Before org B will accept a summary issued by org A, an **active** federation trust relationship must exist between the two orgs — the same invite/accept bilateral peering mechanism that predates this protocol (`POST /v1/federation/invite` → `POST /v1/federation/{id}/accept`). Trust Summaries ride on top of that relationship; they do not replace it or substitute for it. An org with no federation peering to the issuer is denied with `no_active_federation_trust`, identical to the pre-existing raw-chain cross-org path this protocol runs alongside (§5).

If the peering carries a `policy_id` override, it is applied to the resulting decision exactly as it already was for the raw-chain cross-org path.

## 3. Trust Anchor Resolution

**When multiple orgs are tenants of a single shared AGF deployment instance, resolving "the issuer's signing key" means resolving that deployment's shared platform key, not each tenant org's own individually registered public key.** This follows directly from Spec 24 §4's signing model: every Trust Summary produced by a single-instance deployment is signed with that deployment's platform key regardless of which tenant org called `/summarize`, so verifying against a tenant's self-registered key would only succeed by coincidence — where a tenant happened to register the platform's own key as its own, which no real, independently-operated org would do.

For a genuinely separate, independently-operated AGF deployment presenting a summary it signed with its own key, the verifier MUST resolve that key via the federation-registry path, with a TTL-cached lookup (default 3600 seconds). Same-deployment tenants never exercise this path — verification for them always resolves the shared platform key directly.

## 4. Zone Trust Decay

Spec 03 §3.3 describes trust adjustments as a decision crosses zone boundaries. This protocol applies exactly one such adjustment for the `domain_to_global` transition: a fixed −10, applied once, after the existing reputation-penalty step and before risk combination, clamped to `[0, 100]`. The other two transitions §3.3 describes (`local_to_domain`, `global_to_domain`) are Zone 1 (SDK-local-cache) concerns, not part of this cross-org relay, and are not separate numeric adjustments here — Zone 1's local cache either serves an unmodified prior decision or runs the offline risk-penalty table (Spec 03 §4.1), neither of which is a "trust decay" step distinct from what's described here.

## 5. `/v1/decide` Integration

`POST /v1/decide` accepts a `trust_summary` object as an alternative to `chain` — the two are mutually exclusive per request (enforced by a request-model validator). This is additive: the pre-existing raw-chain cross-org path (a `chain` whose first token's issuer resolves to a different org, gated by the same federation-trust check) is untouched and continues to work exactly as before. When `trust_summary` is present:

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

Separate from Trust Summary relay, but part of the same requirement set: revocation propagation latency within a domain SHOULD be measured and alerted on, not silently unmonitored, for revocation backends that support a real push event to measure against (see Spec 05 for backend options). An implementation using a push-based revocation backend SHOULD log an alert and expose a metric when propagation latency past a revocation event exceeds a configurable target (default 60s, per Spec 03 §4.2). This is **measurement and alerting, not enforcement** — a slow propagation is logged, not prevented or retried. Backends using a flat cache-based staleness window instead of push events are out of scope for this target; that is a different, already-documented tradeoff (Spec 05).

**Cross-org revocation staleness is a separate, unsolved problem, deliberately left at TTL-only for this version.** A Trust Summary carries `chain_hash`, not the underlying chain's JWT `jti`s — a receiving org holding only a summary has no revocation-table key to check, and by design cannot ask the issuing org synchronously without coupling every cross-org decision's latency and availability to a remote org (rejected explicitly during design). The summary's own TTL (5 minutes, Spec 24 §5) is the only bound on how stale a cross-org decision's revocation state can be. **Planned but not built**: a signed, push-based federation revocation-sync mechanism — issuing orgs publish signed revocation events to their federation peers, who apply them to a local cache, so no synchronous lookup is ever needed at decide-time. This is explicitly a future protocol revision, not a gap silently left unaddressed; see Spec 27 §5 for how this could eventually generalize past bilateral federation to the full registry model.

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
