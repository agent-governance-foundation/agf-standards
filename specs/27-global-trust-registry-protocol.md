# Specification 27: Global Trust Registry Protocol (AGF-GTR-1.0)

**Version:** 0.1.0 (Draft)
**Status:** Working Draft  
**Supersedes:** Spec 03 §6 (Global Zone Protocol) for this specific topic — Spec 03 remains the normative source for the overall three-zone model itself

## 1. Introduction

Specs 24-26 define how two orgs that already have a bilateral federation relationship (Spec 26 §2) exchange and verify Trust Summaries. That model has a hard ceiling: it only works for orgs that have explicitly peered with each other in advance. It has no answer for the question Spec 03 §6 originally posed — how does an org establish trust with another org it has *no* prior relationship with, verifiably and without a manual out-of-band peering step?

This spec defines the protocol for that: a **Global Trust Registry**, operating as a read-only, cryptographically-verifiable directory of domain trust anchors that any two AGF-compatible deployments can consult, independent of whether they've bilaterally peered. It is deliberately specified as a protocol only, with no reference deployment. Standing up and operating a registry service that other organizations trust as a neutral third party is an infrastructure and governance decision for the AGF Foundation to make, not an engineering task any single deployment can unilaterally take on — see §6.

## 2. Registry Discovery

A domain trust anchor is published at a well-known location:

```
https://<domain>/.well-known/agf-trust-anchor.json
```

```json
{
  "domain": "acme.com",
  "anchor_did": "did:agf:acme:service:trust-anchor",
  "verification_method": [{"id": "...", "type": "JsonWebKey2020", "publicKeyJwk": {...}}],
  "valid_from": 1735603200,
  "valid_until": 1767139200,
  "status": "active"
}
```

The registry itself aggregates these into a signed bundle:

```json
{
  "anchors": [ { "...": "one entry per participating domain" } ],
  "signature": "...",
  "timestamp": 1735603200
}
```

Domain authorities SHOULD cache the bundle with a TTL (default: 1 hour) — the same caching precedent already established for bilateral trust-anchor resolution in Spec 26 §3, generalized to a registry-wide fetch instead of a single peer lookup.

## 3. Cross-Domain Delegation Without Prior Peering

1. Org A's PDP validates its own internal chain (Spec 02), exactly as it would for any Trust Summary (Spec 24).
2. Org A queries the Global Registry for org B's trust anchor — no bilateral federation trust relationship is required for this lookup, unlike Spec 26 §2's model.
3. Org A issues a Trust Summary (Spec 24) whose signature is verifiable against org A's **own** registry-published anchor, not a shared platform key — this is the one place this protocol's signing model genuinely differs from Spec 26 §3's shared-platform-key shortcut, because there is no shared platform for two unrelated orgs to trust.
4. Org B receives the summary, resolves org A's anchor from the registry (§2), and verifies against it.
5. Org B applies its own policy to the request — the registry establishes identity and a root of trust, never authorization.

## 4. Trust Anchor Rotation

An anchor's `verification_method` MAY be rotated. A registry entry undergoing rotation MUST publish both the outgoing and incoming keys for an overlap window, so a summary signed just before rotation and verified just after doesn't spuriously fail. The exact overlap window is a registry-operational parameter, not fixed by this spec.

## 5. Revocation Propagation

Generalizes Spec 26 §8's stated future direction beyond bilateral federation: a domain revoking a delegation publishes a signed revocation event to the registry; participating domains that have previously relied on that domain's trust anchor apply the event to their local cache. No synchronous lookup is required at decide-time — this is the same architectural preference already established in Spec 26 §8 (push, not pull), just generalized from "peer-to-peer between two bilaterally federated orgs" to "any domain that has ever consulted this anchor."

## 6. Dispute Resolution

If two domains disagree about a delegation's validity — one claims a chain was valid at decision time, the other claims it was already revoked — each submits its evidence (chain signatures, revocation state at time of decision, policy versions in effect) to the registry operator's dispute process. The registry operator issues a binding ruling for certified implementations and publishes it as a dispute record. **This requires a registry operator with standing to arbitrate between independent organizations** — necessarily the AGF Foundation or an equivalent neutral body, not any single participating deployment. This is the clearest illustration of why this spec stays protocol-only: the mechanism can be fully specified without anyone having built or operated the service it describes.

## 7. Relationship to Specs 24-26

Specs 24-26 are not a subset of this spec waiting to be extended — they are a **complete, independently useful protocol** for the case that actually exists today (two orgs that have deliberately established a federation relationship). This spec is what a *third* org, with no such relationship, would need instead. A future implementation of this spec should reuse Spec 24's Trust Summary format and Spec 25's canonicalization unchanged; only trust-anchor *resolution* (this spec's §2-3) differs from Spec 26 §3's bilateral/platform-key model.

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
