# Specification 30: Execution-Time Authorization Validation

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None — new specification, per RFC 0000-execution-time-authorization-validation  
**Layer:** Profile

## 1. Introduction

RFC 0000-single-check-decision-semantics made normative that an authorization Decision is evaluated
once, at issuance, and that dispatching an already-issued Decision is not itself a new authorization
evaluation. That RFC documented, but deliberately did not close, the resulting gap: a Decision that
was correct when issued can become stale — its underlying Authority revoked or expired — before the
Action it authorized is actually dispatched.

This specification defines **Execution-Time Authorization Validation**: an optional security control
a Policy Enforcement Point (PEP) MAY perform immediately before dispatching a previously issued
Decision, to check whether the specific Authorities that Decision relied on are still valid at the
moment of dispatch. It is narrow by design — it checks only what can actually change between decision
time and dispatch time (revocation, expiry, platform emergency-halt state), not signatures, chain
structure, scope, or policy, none of which can change on an already-verified chain.

This specification does not modify Spec 00's kernel. It defines a Profile-layer mechanism and a
Core-format artifact that reference the existing kernel Decision and Invalidation objects (Spec 00
§3.4, §3.6) without redefining them, consistent with Spec 00 §2's layering model.

## 2. Relationship to Other Specifications

- **Spec 00 (AAP-Core)**: this specification's check operates on an already-issued kernel Decision's
  `authority_refs` and produces results that reference the kernel Invalidation object where
  applicable. It does not add a seventh kernel object — implementing this specification is OPTIONAL,
  which is inconsistent with kernel status (Spec 00 §1: kernel objects are things "every conformant
  implementation MUST support").
- **Spec 05 (Revocation and Branch Cut Model)**: this specification's revocation check reuses Spec 05's
  existing revocation state — the branch-cut model (Spec 05 §3) applies unchanged: an ancestor
  Authority's revocation invalidates its descendants at execution time exactly as it does at decision
  time. This specification does not define a new revocation mechanism or a new propagation guarantee;
  see §7.
- **RFC 0000-single-check-decision-semantics**: this specification is the "future RFC" that RFC
  explicitly reserved room for. That RFC's decision-lifecycle semantics (evaluate once, dispatch
  later) are unchanged by this specification — this specification adds an optional check at dispatch
  time; it does not turn dispatch into a new authorization evaluation.
- **Spec 10 (API Protocol)**: the API surface in §5 follows Spec 10's conventions (response envelope,
  error codes, versioning).

## 3. The Execution Gate Check

Immediately before dispatching an already-issued Decision with `status` `ALLOW` (with or without the
`caution` qualifier), a PEP performing this control checks, in any order:

### 3.1 Platform state

The deployment is not under an emergency halt (Spec 05 §8.4). If halted, the result is `invalid` with
reason `platform_halted`.

### 3.2 Revocation

For each id in the Decision's `authority_refs` (Spec 00 §3.4): no Invalidation record (Spec 00 §3.6)
exists with `cause` `revoked` or `superseded` whose `subject` is that Authority id, or an ancestor of
it in its delegation lineage (Spec 02 `parent` chain). This is the same branch-cut traversal Spec 05
§3.3 already defines, applied at dispatch time instead of decision time. If any Authority or ancestor
is found invalidated this way, the result is `invalid` with reason `authority_revoked`, and the
specific Invalidation record(s) found are referenced in the check's output (§4) — this control
discovers a pre-existing fact; it does not create a new Invalidation record itself.

### 3.3 Expiry

For each id in the Decision's `authority_refs`: the current time has not passed that Authority's
`expires_at` (Spec 00 §3.2). If any has expired, the result is `invalid` with reason
`authority_expired`.

### 3.4 What this check explicitly excludes

A conformant implementation of this specification MUST NOT, as part of this check:

- Re-verify any Authority's signature.
- Re-run chain structural validation (continuity, depth, cycle checks — Spec 02).
- Re-evaluate scope or policy (Spec 06).
- Compute a fresh trust or risk score.

None of the above can have changed since decision time on the same, already-issued Decision. An
implementation that has reason to believe one of them might have changed (e.g. it is evaluating a
different Action, or a policy version was superseded) MUST perform a new authorization evaluation
through the normal decision path — that is out of scope for this specification, which covers dispatch
of the *same*, already-authorized Action under the *same*, already-issued Decision.

## 4. Execution Validation Record

The AGF serialization of "a check was performed, and what it found." This is a Core-format artifact,
not a kernel object — it correlates to the kernel Decision object (`decision_ref`) and, when
applicable, to existing kernel Invalidation records (`invalidation_refs`); it does not extend Spec 00.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Unique identifier of this validation record |
| `decision_ref` | string | Yes | `id` of the Decision (Spec 00 §3.4) this check was performed for |
| `authority_refs_checked` | array of string | Yes | The specific Authority `id`s checked — normally all of `decision_ref`'s `authority_refs` |
| `checked_at` | number | Yes | Unix timestamp when the check was performed |
| `result` | string | Yes | `valid` or `invalid` |
| `reasons` | array of string | No (empty when `valid`) | Machine-readable reasons for `invalid`: `authority_revoked`, `authority_expired`, `platform_halted` — more than one MAY apply |
| `invalidation_refs` | array of string | No (empty unless `authority_revoked` applies) | `id`s of the pre-existing Invalidation record(s) (Spec 00 §3.6) that caused the result |
| `checked_by` | string | Yes | Actor `id` of the PEP that performed the check |

An implementation MUST persist an Execution Validation Record for every check it performs, whether
the result is `valid` or `invalid` — an all-`valid` history is itself the evidence that this control
was actually exercised, not skipped, which matters for the same reason Spec 00 §7.3 treats the
Receipt `unknown`-outcome rate as a monitored metric: a control that is never actually invoked
provides no security benefit regardless of what this specification says about it.

## 5. API Contract

Per Spec 10 conventions (response envelope, `/v1/` versioning).

**`POST /v1/decisions/{artifact_id}/validate-execution`** — Perform the check of §3 against the named
Decision and return the result. Like `POST /v1/decide` (Spec 10 §5.5), an `invalid` result is a normal
200 response, not an HTTP error — the caller decides what to do with the result, this endpoint reports
it.

Response:

```json
{
  "data": {
    "execution_validation_id": "xv_1735603302_f9a8b1",
    "decision_ref": "dec_1735603300_a1b2c3",
    "result": "invalid",
    "reasons": ["authority_revoked"],
    "invalidation_refs": ["inv_1735603301_c7d4e2"],
    "checked_at": 1735603302
  }
}
```

**`GET /v1/decisions/{artifact_id}/execution-validations`** — All Execution Validation Records
correlated to a Decision, following the same query-surface pattern as Spec 10 §5.6's
`GET /v1/receipts?decision_ref={artifact_id}`.

This specification does not define a new error code — a request naming an `artifact_id` with no
matching Decision uses the existing `NOT_FOUND` code (Spec 10 §4.3).

## 6. Built-in Gateway Integration

Whether a reference implementation's own built-in PEPs (protocol gateway adapters, Specs 21-23)
perform this check by default is an implementation decision, not something this specification
mandates. Where a built-in PEP already evaluates the Decision and dispatches in the same request,
with no meaningful time gap between them, the marginal security benefit of also performing this check
is small relative to a PEP acting on a portable Decision artifact fetched at an earlier, unbounded
time — but it remains available at near-zero marginal cost (the checks in §3 are targeted lookups and
claim reads, not chain re-verification), and an implementation MAY perform it on every dispatch path
uniformly for consistency and defense-in-depth rather than only where the time gap is largest.

## 7. Interaction with Spec 05 §5.5 Propagation Guarantees

This specification's revocation check (§3.2) consults the same revocation-state mechanism already in
use for decision-time evaluation — it does not define a new one, and it does not change Spec 05 §5.5's
propagation targets or Spec 28's same-transaction zero-latency property. A revocation not yet visible
to that mechanism at the moment of this check is not caught by this check, for exactly the reasons
Spec 05 §5.5 and Spec 28 §4.3 already describe for decision-time evaluation. This specification
narrows the window during which a stale Decision can be dispatched — from the Decision's entire
dispatchable lifetime down to the interval between this check and the actual dispatch call — it does
not claim to make that interval zero.

## 8. Security Considerations

### 8.1 What this closes and what it does not

See §7 — this control narrows, rather than eliminates, the decision-to-dispatch staleness window. A
revocation recorded after this check but before dispatch completes is not caught. Implementations
SHOULD minimize the gap between performing this check and the actual dispatch call.

### 8.2 Relationship to Spec 00 §7.1 and KERNEL-NEG-02

Spec 00 §7.1 establishes that a Decision or Receipt is evidence, not authority; KERNEL-NEG-02
requires that a stored `ALLOW` MUST NOT be honored as bearer authority for a new request. This
control does not weaken either: it can only add a `DENY` outcome relative to what the original
Decision already permitted, never grant authorization the original Decision did not already grant. An
implementation MUST NOT use this specification's mechanism to authorize a different Action or a
different Authority set than the one the original Decision covered — that is a new authorization
evaluation, governed by normal decision semantics, not this specification.

### 8.3 No new attack surface

The checks in §3 are read-only and reuse mechanisms Spec 05 (revocation) and the kernel Authority
object (expiry) already define. This specification composes existing checks at a new point in the
request lifecycle; it introduces no new trust anchors, signing keys, or write paths.

## 9. Non-Goals

- Not a second full authorization evaluation — §3.4 lists what this control explicitly does not
  re-check, and why.
- Not a replacement for decision-time authorization, and not a claim that the decision-to-dispatch
  window can be made zero — see §7, §8.1.
- Does not mandate that built-in reference-implementation gateways enable this control by default —
  see §6.
- Does not add a seventh kernel object to Spec 00, or modify the meaning of the existing six — see
  §2.
- Does not define a new revocation distribution or propagation mechanism — see §7.

## 10. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-08-13 | Initial public working draft, per RFC 0000-execution-time-authorization-validation |
