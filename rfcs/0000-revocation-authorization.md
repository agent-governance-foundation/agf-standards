# RFC 0000: Revocation Authorization

- **Author(s):** Ramesh Kalimuthu
- **Affected spec(s):** Spec 05 §4.3 (Revocation Entry), new §4.3.2
- **Status:** Draft
- **Discussion:** (none yet — draft)

## Summary

Requires that a revocation only be honored if the revoking entity is the target delegation's direct grantor, or is represented by an ancestor delegation in the target's parent lineage (per Spec 02 `parent` lineage) — consistent with the branch-cut model's own principle (§2: "revocation targets authority... only the specific delegation path is severed") that authority to cut a branch should itself derive from authority over that branch. This proposal deliberately does not say "valid, unrevoked ancestor": whether the ancestor delegation must itself remain valid at revocation time, or merely have existed in the chain lineage, is left to Unresolved Questions rather than silently decided by the proposal's wording.

## Motivation

Keep four things distinct throughout this RFC, rather than blending them into one narrative:

```
AGF current specification
        ↓
silent on revocation authorization

agf-runtime current implementation
        ↓
allows any authenticated org member to revoke

RFC proposal
        ↓
grantor-or-ancestor authorization

future runtime PR
        ↓
enforce accepted RFC (separate, not part of this RFC)
```

### Specification gap

Spec 05 §4.3 requires a `revoked_by` field ("DID of revoking entity") on every revocation entry, but places no constraint on who that DID may belong to. An implementation can accept a revocation from any caller and still claim conformance — the specification is silent, not permissive by design; it simply never addressed the question.

### Current runtime behavior

At the time of this RFC, the referenced `agf-runtime` implementation permits any authenticated organization member to revoke any delegation within that organization, regardless of their relationship to it. Verified directly against current source:

1. `DelegationService.revoke_delegation()` (`agf-runtime/src/application/services/delegation_service.py:86-129`) fetches the target delegation scoped only by `org_id` (`repo.get(delegation_id, org_id)`) and, once found and not already revoked, unconditionally revokes it. `revoked_by` is recorded on the resulting `RevocationRecordRow` purely for audit provenance — it is never checked against the target delegation's `iss` or ancestor chain before the revocation is honored.
2. `POST /v1/delegations/{delegation_id}/revoke` (`agf-runtime/src/presentation/api/routes/delegations.py:184-204`) depends only on `Depends(get_auth)` — no `require_tier`, `require_role`, or admin dependency, unlike other routes in the same codebase that do gate on tier (e.g. the gateway-proxy routes use `require_tier("growth")`). The same pattern holds for the bulk `POST /{delegation_id}/revoke-branch` endpoint (lines 212-251).
3. `get_auth` (`agf-runtime/src/presentation/api/auth.py:368-373`) only requires that the request was successfully authenticated — it imposes no role or tier restriction. `AuthContext.role` (`auth.py:77`) can be `"owner"`, `"admin"`, `"viewer"`, or `"super_admin"`; `get_auth` does not distinguish between them.

This is stated as an observation about a specific, named, currently-existing implementation at the time of writing — not as a claim about what the specification requires or endorses. `agf-runtime` is free to change this at any point during this RFC's discussion period, which is exactly why the temporal framing above matters.

### Security impact

Concrete attack scenarios this gap permits today: a low-privilege compromised account (e.g. a `"viewer"`-role credential, typically considered lower-value) revoking a critical production agent's delegation as a denial-of-service; or an attacker revoking a security team's own monitoring/incident-response delegation to blind detection during an active compromise.

### Why the proposed model

Grantor-or-ancestor authorization mirrors a principle Spec 05 §2 already states — "revocation targets authority... only the specific delegation path is severed" — rather than inventing a new authorization concept. If authority to grant flows down a delegation chain, authority to cut a branch of that chain should itself derive from authority somewhere on that branch, not from organizational membership alone.

## Proposed change

New §4.3.2, "Revocation Authorization," immediately following the existing §4.3 Revocation Entry table and its §4.3.1 Invalidation Mapping subsection.

### Normal grantor/ancestor authorization

> A revocation MUST only be honored if the revoking entity is the direct grantor of the target delegation, or is represented by an ancestor delegation in the target's parent lineage.

The proposal establishes the authorization relationship at the normative level but does not prescribe the exact identity-binding mechanism required to determine that relationship. That mechanism is an unresolved interoperability question (see Unresolved Questions) — deliberately, so that two conformant implementations are not free to silently diverge on what check they actually run while both claiming compliance.

### Unauthorized revocation rejection

> Implementations MUST reject unauthorized revocation attempts with an error that unambiguously indicates revocation authorization failure.

This RFC does not lock the exact wire error code here (see Unresolved Questions). `REVOCATION_UNAUTHORIZED` is used elsewhere in this RFC only as a proposed example name.

### Emergency §8.4 exception

> Normal revocation authorization is governed by the grantor-or-ancestor rule. An implementation MAY additionally support the emergency revocation procedure defined in §8.4, under which an authorized emergency actor outside the delegation lineage may revoke authority.

This is an explicit exception to the normal rule, not a third form of grantor/ancestor authorization — this RFC extends §8.4 to serve as that exception's basis; §8.4's existing text did not itself already imply this.

### Audit requirements

> An emergency revocation MUST provide distinct audit provenance and MUST explicitly indicate that the normal grantor-or-ancestor authorization rule was bypassed. The emergency actor MUST NOT thereby be represented as the target's grantor or ancestor.

Plus: the emergency procedure invoked MUST be one documented under §8.4.

## Backward compatibility

This doesn't change wire format, but it narrows previously-unconstrained behavior for any implementation — including `agf-runtime` today — that doesn't yet enforce it. Recommended version impact: a Minor version increment, subject to the specification version current at the time the accepted RFC is incorporated (not hardcoded here, since Spec 05 currently sits at 0.3.0 (Draft) and this RFC may or may not be incorporated in the same PR as RFC 0000-single-check-decision-semantics, which also targets Spec 05 — if both land together that's a single 0.3.0 → 0.4.0; if separately, the second becomes whichever the next minor version is at that time).

Open question for maintainers, kept explicit rather than resolved here: narrowing previously-unconstrained behavior is arguably a larger compatibility question than a pure documentation addition (compare RFC 0000-single-check-decision-semantics), and maintainers may judge Major more appropriate than Minor for this specific RFC.

## Security considerations

### Compromised low-privilege member

Closes (once implemented — see below) the scenario where a low-privilege compromised credential can revoke any delegation in the org as a denial-of-service against unrelated agents.

### Monitoring/response delegation

Closes (once implemented) the scenario where an attacker revokes a security team's own monitoring or incident-response delegation to blind detection during an active compromise.

### Current runtime gap remains until follow-up implementation

Accepting this RFC does not itself close the `agf-runtime` gap described in Motivation. A follow-on `agf-runtime` implementation PR is required to actually enforce the grantor-or-ancestor rule. Given the security sensitivity of an authorization-boundary change, that follow-on should go through this workspace's review-record process (`agf-profile/implementation/review-records/`, `RR-NNNN`, precedent: `RR-0001-saml-connector.md`) before merging enforcement code. This is a recommendation made by this RFC, not something this RFC commits to or performs.

## Alternatives considered

**(a) Do nothing / formalize the current lax behavior as the accepted model.** Rejected: leaves the denial-of-service and detection-blinding scenarios above open indefinitely, with no path to closing them.

**(b) Grantor-only (no ancestor).** Rejected as too strict: breaks the legitimate case of a security team cutting a branch above a compromised mid-chain agent without itself owning that specific delegation — exactly the branch-cut model §3 already describes as a normal operation.

**(c) Role-based (org-admin only), as the sole mechanism.** Rejected as the sole mechanism: "org-admin" is an implementation/RBAC concept (specific to how a given deployment models organizational roles), not an AGF-native one grounded in the delegation chain itself. It remains available as a basis for the emergency-procedure exception, but not as the normal-path rule.

## Unresolved questions

**Actor-to-delegation binding** (most fundamental — listed first because "grantor-or-ancestor" only becomes meaningful once this is answered, and two implementations could otherwise both claim compliance while performing different checks): how must an implementation establish that the revoking actor is the direct grantor (actor identity corresponds to the target delegation's `iss`) or is authorized by an ancestor delegation in the target's parent lineage (actor identity corresponds to the issuer/holder of some ancestor delegation)? This RFC does not guess at the exact field-level mechanics.

**Error-code status:** `REVOCATION_UNAUTHORIZED` is a proposed example name only; whether this becomes a kernel error code or remains implementation-defined is unresolved.

**Ancestor validity semantics:** whether "ancestor" requires the ancestor delegation to still be valid/unrevoked at revocation time, or merely to have existed in the chain lineage — intentionally left open, not resolved by the main proposal's wording.

**Emergency-role definition boundary:** exactly what qualifies as the "authorized emergency actor" in the §8.4 exception is implementation-defined; whether the specification should say more is open.
