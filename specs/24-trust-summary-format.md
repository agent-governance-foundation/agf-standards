# Specification 24: Trust Summary Format (AGF-TS-1.0)

**Version:** 0.1.0 (Draft)
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Profile  

## 1. Introduction

Spec 03 (Trust Zones) describes a Global zone for cross-organization delegation, but deliberately does not require replaying a full delegation chain across an org boundary — doing so would mean every receiving org re-validates every hop of a chain it has no direct relationship with, and exposes the full internal shape of another org's delegation tree to whoever it transacts with.

This spec defines the **Trust Summary**: a short-lived, signed protocol artifact that stands in for a fully-verified delegation chain in a cross-org exchange. It is a **compression of what's transmitted, never of what's verified** — the issuing org validates every hop of the underlying chain exactly as it would for a same-org decision (Spec 02), and only then produces a summary of the result. No signature in the original chain is ever skipped to produce one.

This is deliberately specified as a versioned wire protocol, not described only as a runtime implementation detail, so any AGF-compatible implementation can produce and verify these artifacts.

## 2. Core Principle

**Trust is portable. Risk is contextual.** A Trust Summary conveys the delegation chain's validated identity and trust — it never carries a risk score. The receiving org's own PDP always computes risk itself, per action, at decide-time, exactly as it does for a same-org request. This preserves each org's policy sovereignty: the same action can legitimately be scored differently by different orgs, and a Trust Summary must never bias that. It also means a single summary is reusable across every action within its `effective_scope` for the duration of its TTL, rather than needing to be re-issued per action.

## 3. Schema

```json
{
  "version": "AGF-TS-1.0",
  "issuer_org": "did:agf:acme:org:root",
  "subject_org": "did:agf:example:org:root",
  "origin_agent": "did:agf:acme:alice",
  "current_agent": "did:agf:acme:agent:deployer",
  "delegation_depth": 3,
  "effective_scope": ["orders.read", "orders.write"],
  "chain_hash": "<sha256 hex>",
  "chain_hash_algorithm": "SHA-256",
  "canonicalization": "AGF-C14N-1.0",
  "policy_version": "active_<org_id>",
  "delegation_trust_score": 87,
  "trust_algorithm": "AGF-Trust",
  "trust_algorithm_version": "1.0",
  "issued_at": 1735603200,
  "expires_at": 1735603500,
  "signature": "<base64url DER ES256>"
}
```

| Field | Type | Description |
|---|---|---|
| `version` | string | Fixed `"AGF-TS-1.0"`. A verifier that doesn't recognize the version rejects outright — no best-effort parsing of unknown versions. |
| `issuer_org` | string (DID) | The org whose PDP validated the underlying chain and vouches for this summary. |
| `subject_org` | string (DID) | The intended recipient org — binds the summary to whoever it was issued for (§5). |
| `origin_agent` | string (DID) | `chain[0]`'s issuer. |
| `current_agent` | string (DID) | `chain[-1]`'s subject — the acting principal. |
| `delegation_depth` | integer | Number of hops in the underlying chain (`len(tokens) - 1`, same convention as Spec 02's `chain_depth`). |
| `effective_scope` | array of strings | The intersected scope across the chain (Spec 02 §3.5), sorted. |
| `chain_hash` | string | See Spec 25 — a hash of the chain's semantic claims, deliberately excluding derived scores. |
| `chain_hash_algorithm` | string | Fixed `"SHA-256"`. |
| `canonicalization` | string | Fixed `"AGF-C14N-1.0"` — see Spec 25. |
| `policy_version` | string | The policy version in effect on the issuing org's side at build time. |
| `delegation_trust_score` | integer 0-100 | The chain's structural trust score (Spec 02/04), before any zone-transition decay (Spec 26 §4). No `risk_score` field exists anywhere in this schema — see §2. |
| `trust_algorithm` | string | Identifies which scoring formula produced `delegation_trust_score`, so a receiving implementation knows how to interpret it. Fixed `"AGF-Trust"`. |
| `trust_algorithm_version` | string | Version of that formula. Fixed `"1.0"`. |
| `issued_at` | integer (unix seconds) | When this specific summary was built. |
| `expires_at` | integer (unix seconds) | `issued_at + TTL` (default: 300s / 5 minutes). |
| `signature` | string | Base64url-encoded DER ES256 signature over the canonicalized form of every other field (§4). |

## 4. Signing

The signature covers the RFC-8785-inspired canonical serialization (Spec 25) of every field above except `signature` itself — a signature can never sign itself.

**When a Trust Summary is issued by a single-instance, multi-tenant AGF deployment, it MUST be signed with that deployment's shared platform key**, not a key unique to the issuing org — such a deployment never holds any org's individual private key (only a caller-supplied, public-only key is registered at signup). A Trust Summary therefore represents "the platform validated this org's chain and vouches for the summary," using the same custody model already used for audit artifacts (Spec 07), not "org A cryptographically signed this with its own key." Verification (`POST /v1/decide` accepting a `trust_summary`, and `POST /v1/delegations/verify-summary`) MUST check against that same platform key, not the issuer's self-registered public key, for same-deployment tenants — see Spec 26 §3 for why resolving the issuer's own registered key would be wrong in this topology.

If a genuinely separate, independently-operated AGF deployment is the issuer (over the existing bilateral federation HTTP path — Spec 26 §2), that deployment signs with its own key, and the receiving deployment verifies against that peer's registered public key instead. Both signers MUST use the same signature algorithm (ES256, per §2); only key resolution differs by deployment topology.

## 5. Validity Rules

- **TTL.** Default 300 seconds, matching Spec 03's Local zone cache TTL. A verifier applies a 30-second clock-skew allowance past `expires_at` before treating a summary as expired.
- **Subject binding.** `subject_org` binds the summary to its intended recipient. Verification fails if the org actually presenting the summary — resolved from the presenting org's own authenticated session, never from a claim inside the summary itself (see Spec 26 §6 for why this check must not be self-referential) — is not `subject_org`.
- **Multi-use within TTL.** A summary is not single-use or nonced. The presenting org must still separately authenticate its own session for every request it makes; the summary is not a bearer credential on its own. `subject_org` binding is what prevents a different, unintended org from replaying it, not per-use consumption.
- **Version/canonicalization/hash-algorithm fields must all be recognized values.** Any unrecognized value is a rejection, not a best-effort parse.

## 6. Endpoints

- `POST /v1/delegations/summarize` — validates a submitted chain via the normal Spec 02 chain-validation path; on success, builds and signs a Trust Summary. Requires `subject_org`, `action_scope`, `audience` alongside the chain.
- `POST /v1/delegations/verify-summary` — verifies a summary's signature, version, canonicalization, expiry, and subject binding against a caller-supplied public key. This endpoint's scope is deliberately narrow: it does not perform federation-trust-relationship lookup (Spec 26 §2 covers where that check actually lives, in the `/v1/decide` integration) — it exists so any implementation can check whether a given summary and key are consistent, including for interoperability testing between independent implementations.

## 7. Relationship to Other Specs

- Spec 25 defines the canonicalization (`AGF-C14N-1.0`) this format's signature and `chain_hash` depend on.
- Spec 26 defines the end-to-end relay protocol this artifact travels through — issuance, transmission, verification, and the federation-trust prerequisite that gates whether two orgs can exchange summaries at all.
- Spec 03 §2.3/§6 describes the Global zone concept this artifact implements a concrete instance of, without adopting §6's standalone global-registry design — see Spec 27.

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
