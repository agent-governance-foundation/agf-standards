# Specification 30: Execution-Time Authorization Validation

**Version:** 0.3.0 (Draft)  
**Status:** Working Draft — §3-6 (the execution-time check, its API contract, and optional gateway
integration) has a reference implementation, reachable both as a direct API call for custom Policy
Enforcement Points and via at least one client SDK.  
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
`caution` qualifier) — or a `REVIEW_REQUIRED` Decision through approved execution (§3.5), which adds
the requirements of that section — a PEP performing this control checks, in any order:

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

### 3.5 Approved `REVIEW_REQUIRED` Decisions

A `REVIEW_REQUIRED` Decision (Spec 00 §4) must not proceed until a human judgment is rendered, or
until an escalation timeout policy the organisation explicitly configured permits proceeding without
one (Spec 15 §5). These are different: a **human approval** (`outcome: approved`) is a judgment by a
person; a **policy continuation** (`outcome: continued_by_timeout_policy`) is the organisation's
advance choice to proceed when no one responded, is not an approval, and is eligible only under Spec
07 §11.8 rule 5. This section defines the only way such a Decision proceeds afterwards: **approved execution** dispatches the
*same*, already-issued Decision *D* once, for the exact call that was reviewed, after its approval
(Spec 07 §11.4) is verified and its Authorities are revalidated. It is not a new authorization
evaluation (§3.4): nothing is re-scored or re-evaluated, and anything that differs from the reviewed
call is a different Action that MUST go through the normal decision path.

#### 3.5.1 Invocation

- **Through a gateway** (Specs 21–23): the caller re-presents the reviewed call, byte-for-byte as
  bound in §3.5.2, together with the approval's identifier (the reference implementation uses a
  request header, `X-AGF-Approval: <approval_request_id>`). On such a request the gateway MUST NOT
  make a new decision; it runs §3.5.4–§3.5.6 for *D*. Without the identifier, a gateway behaves as
  for any other call.
- **Direct callers** that dispatch themselves call `POST /v1/decisions/{artifact_id}/validate-execution`
  with the approval identifier and their binding digest (§5). Their guarantees are narrower (§3.5.8).

#### 3.5.2 Binding document

At decision time, and again on approved execution, the PEP builds one **binding document**: a JSON
object, serialized under AGF-C14N-1.1 (Spec 25 §2.2), describing the complete effective call — what
the PEP would actually send upstream.

| Kind | Fields |
|---|---|
| all | `binding_version` (`1`); `kind`; `org_id` (*D*'s organisation); `caller` (the authenticated principal that made the request, derived the same way as the approval request's `requestor`); `gateway_id`; `audience`; `delegation_chain` (the token strings, in order); `action_type`; `action_resource` |
| `http` | `method`; `destination` (the exact URL dispatched to, without the query); `query` (the raw query string, `""` if none); `headers` (every header the PEP forwards, as `[[lowercase-name, value], …]`, sorted by name, preserving the order of repeated names); `upstream_credential_sha256` (base64url SHA-256 of any credential the PEP injects upstream, or `null`); `body_b64` (base64url of the exact body bytes) |
| `mcp` | `destination`; `jsonrpc_b64` (base64url of the exact JSON-RPC request bytes, including `id`); `headers` (`mcp-session-id` and `mcp-protocol-version`, each if forwarded); `upstream_credential_sha256` |
| `a2a` | `destination`; `jsonrpc_b64` (exact request bytes, including `id`); `upstream_credential_sha256` |
| `direct` | `destination` (the URL or identifier the caller will call); `payload_b64` (the exact bytes it will send) |

Payloads are bound as **exact bytes**. The re-presented call MUST be byte-identical to the reviewed
one, including any JSON-RPC `id`: the reviewed attempt was blocked before reaching the upstream, so
the upstream still receives that `id` once. Payloads are encoded (base64url) **without parsing or
canonicalizing their contents**, so payloads containing decimal numbers or any other JSON are
allowed — and any byte change, including a different number format or key order, changes the
binding and is a mismatch.

**Headers.** Every header the PEP forwards upstream is bound, with its exact value. That includes
`user-agent`, `accept`, `accept-encoding`, `accept-language`, tracing and request-id headers (which
some upstreams use as idempotency keys), and MCP's `Mcp-Session-Id` and `Mcp-Protocol-Version`. No
forwarded header is exempt as "volatile": any of them can change upstream behaviour or session state.
Headers the PEP never forwards (hop-by-hop headers, `content-length`, `host`, the caller's own
credentials, the chain header and the approval identifier) are stripped identically on both
occasions and are not part of the effective call. A header the PEP sets itself is part of the
binding and MUST have the same value on both occasions. Where the PEP's HTTP client would otherwise
add a default header the caller did not send (for example `user-agent`, `accept`,
`accept-encoding`), the PEP MUST set it to a fixed, documented value on both occasions, so a client
library change cannot alter the effective call between review and execution.

**Sessions.** This version defines **no** equivalence rule for MCP sessions. A different or expired
`Mcp-Session-Id` is a binding mismatch; executing under a new session requires a new review.

#### 3.5.3 Request binding digest

- `binding_sha256` = SHA-256 of the binding document's AGF-C14N-1.1 bytes, encoded base64url without
  padding: a **43-character ASCII string**.
- `request_binding` = `HMAC-SHA256(key = salt, message = UTF-8 bytes of binding_sha256)`, base64url
  without padding, written `{"alg": "HMAC-SHA256-SALT16", "value": "<digest>"}`. This is the salted
  digest construction, text-field input encoding and value format of Spec 07 §11.2. The HMAC input is
  the 43-character string, **not** the 32 raw digest bytes, which §11.2 does not define as an input.
- `request_binding` is recorded in *D*'s `request.context` for every gateway decision, whatever the
  gateway's logging settings, and for every direct decision whose caller supplies `binding_sha256`. It
  is signed as part of *D*.
- **Salt:** 16 bytes from a cryptographically secure random source, one per Decision, generated at
  decision time and stored by the implementation, never in any signed payload. Unlike the evidence
  fields of Spec 07 §11.2, the plaintext (`binding_sha256`) is **not** stored: it is recomputed from the
  re-presented call (gateways) or presented again by the caller (direct). The salt is retained and
  erased with *D* (Spec 07 §5.2, §7); once it is erased, *D* can no longer be executed.
- A Decision with no `request_binding`, or whose salt is missing or erased, is **not bindable** and
  never eligible for approved execution.

Test vectors: `schemas/fixtures/request-binding.vectors.json` (checked by `schemas/check.py`),
including a negative vector showing that the raw-32-byte input yields a different value.

#### 3.5.4 Eligibility

All of the following MUST hold, evaluated on **signed records only** — never on mutable approval
state (an implementation's approval status field can read "approved" for a timeout that continued by
policy):

1. A verified approval request record *R* and approval attestation *A* (Spec 07 §11.3, §11.4) for the
   named approval, bound to each other and to *D* as in Spec 07 §11.8 rule 1.
2. *A* is `format_version` `"1.1"` with a non-null `execution_not_after`. A 1.0 attestation is never
   sufficient, independently of whether *D* is bindable.
3. `A.outcome = approved` (human approval); or `A.outcome = continued_by_timeout_policy` (policy
   continuation, not an approval) only under Spec 07 §11.8 rule 5. Any other outcome is not a grant.
4. The current time is not later than `A.execution_not_after`.
5. *D* is bindable (§3.5.3), and the recomputed `request_binding` equals *D*'s. The request's
   organisation equals *D*'s, and its `caller` equals *R*'s `requestor`.
6. No execution claim exists for *D* (§3.5.6).

#### 3.5.5 Order of checks, expiry and timing

1. Eligibility (§3.5.4). A failure rejects the request: no claim, no Execution Validation Record.
2. Revalidation: the checks of §3.1–3.3, producing an Execution Validation Record *V* (§4) bound to
   *D*.
   - *V* MUST be persisted **and signed** (Spec 07 §11.6). If it cannot be, fail closed: no claim, no
     dispatch, and the approval remains unconsumed. (The ALLOW path may proceed without a stored *V*;
     approved execution may not, because Spec 07 §11.8 needs *V*.)
   - `V.result = invalid` → no claim, no dispatch, approval unconsumed.
   - `V.checked_at > A.execution_not_after` → expired: no claim, approval unconsumed.
3. Immediately before claiming: the current time MUST NOT be later than `A.execution_not_after`, and
   MUST NOT exceed `V.checked_at` by more than **5 seconds**. Otherwise abort, approval unconsumed (a
   later attempt within the window produces a new *V*).
4. Claim (§3.5.6).
5. Immediately before the upstream request: the same two conditions as step 3. If either fails, do
   **not** dispatch; the claim is retained and the approval is consumed without execution.
6. Dispatch exactly once (§6).
7. Record the outcome in a signed Receipt naming *V* (`execution_validation_ref`).

Expiry is therefore checked at eligibility, against the signed `V.checked_at`, before the claim and
before dispatch, at whole-second resolution (`≤ execution_not_after` is in the window). Expiry passing
before the claim leaves the approval unconsumed; expiry passing after it prevents dispatch and retains
the claim. The 5-second limit is independent of expiry.

#### 3.5.6 Consumption

One approval permits **one dispatch attempt per Decision**.

- The implementation MUST enforce, with a database uniqueness constraint or equivalent atomic
  mechanism, at most one execution claim per (*organisation*, *D*) — so that even two approvals for
  the same Decision cannot yield two dispatches.
- The claim is a single atomic write, durably committed **before** dispatch. A conflicting claim
  rejects the request.
- **Uncertain commit:** if the result of committing the claim is unknown (for example, the connection
  failed after the commit was sent), the implementation MUST treat it as **no confirmed claim** and
  MUST NOT dispatch. A later attempt then either finds the claim (and is rejected — the approval is
  consumed without execution) or claims normally.
- A committed claim MUST NOT be released automatically — not on timeout, crash, upstream error or a
  failure to write the Receipt. Executing again requires a new review.

The semantics are **at most once**, not exactly once: an approval may be consumed without the call
reaching the upstream.

#### 3.5.7 Failure behaviour

| Failure point | Claim | Dispatched | Approval |
|---|---|---|---|
| Before the claim commits (crash; eligibility, revalidation or evidence failure; expiry; the 5-second limit) | none | no | unconsumed |
| Claim commit result uncertain | unknown | no | unconsumed or consumed; never executed twice |
| After the claim, before dispatch (crash; expiry or the 5-second limit at step 5) | retained | no | consumed |
| During or after dispatch, before the outcome is recorded (crash) | retained, outcome unknown | unknown | consumed |
| Upstream timeout or connection error | retained, outcome `unknown` | attempted once | consumed |
| Receipt cannot be written after dispatch | retained, outcome recorded without a Receipt | yes | consumed; no Receipt exists for Spec 07 §11.8 to evaluate |

#### 3.5.8 Direct callers

For a direct caller the implementation enforces one claim per Decision (claimed at
`validate-execution` when *V* is valid and signed), the binding digest, the execution window (at
eligibility, against `V.checked_at`, and before the claim), and **exactly one** accepted outcome report
per claim, naming the claimed *V*; further reports are rejected and **not recorded**. It cannot
prevent a direct caller from dispatching repeatedly, or dispatching something else, outside its
gateways; it cannot enforce the delay between validation and the caller's dispatch; and a matching
caller-supplied digest is the **caller's attestation**, not proof of what was sent. Repeated direct
dispatches may therefore be undetectable from signed evidence (Spec 07 §11.8, §11.9).

#### 3.5.9 What the evidence establishes

For an executed Receipt from this path, Spec 07 §11.8 binds *R*, *A* and *V* to *D* and requires
`A.recorded_at ≤ V.checked_at ≤ A.execution_not_after`: signed evidence establishes that **execution
validation occurred within the signed approval window**. The actual dispatch time is not proven by
any signed record. More than one executed Receipt for *D* is `EXECUTED_MORE_THAN_APPROVED`; the
absence of a second Receipt does not prove a single execution (Spec 07 §11.9). The execution claim is
operational state, not evidence.

**Errors** (Spec 10 §4.3): `APPROVAL_NOT_ESTABLISHED`, `APPROVAL_NOT_GRANTED`, `APPROVAL_EXPIRED`,
`APPROVAL_NOT_BINDABLE`, `APPROVAL_CALLER_MISMATCH` (403); `APPROVAL_REQUEST_MISMATCH`,
`APPROVAL_CONSUMED` (409); `APPROVAL_CLAIM_UNCERTAIN`, `EXECUTION_EVIDENCE_UNAVAILABLE`,
`EXECUTION_VALIDATION_STALE` (503).

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

**Signing.** Each Execution Validation Record is also emitted as a signed evidence record (`agf.execution_validation`, Spec 07 §11.6), in the same transaction. If signing fails, the check's result stands and the record is stored unsigned (Spec 07 §11.7) — except on approved execution (§3.5.5), where an unsigned or unpersisted record stops the execution before any claim or dispatch. An Execution Validation Record whose `result` is `invalid`, followed by an executed Receipt, is a violation (Spec 07 §11.8, `EXECUTED_AFTER_FAILED_VALIDATION`).

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

For a `REVIEW_REQUIRED` Decision, `validate-execution` additionally takes `approval_request_id` and
`binding_sha256` (§3.5.3) and performs §3.5.4–§3.5.5 steps 1–4: on success it returns the Execution
Validation Record together with the execution claim; it does not dispatch. `POST
/v1/decisions/{artifact_id}/report-outcome` for such a Decision is accepted exactly once per claim and
only when it names the claimed record (§3.5.8). `POST /v1/decide` accepts an optional `binding_sha256`,
required for a direct caller's `REVIEW_REQUIRED` Decision to be executable later.

A request naming an `artifact_id` with no matching Decision uses the existing `NOT_FOUND` code (Spec 10
§4.3). Approved execution defines the error codes listed at the end of §3.5, added to Spec 10 §4.3.

## 6. Built-in Gateway Integration

Whether a reference implementation's own built-in PEPs (protocol gateway adapters, Specs 21-23)
perform this check by default is an implementation decision, not something this specification
mandates. Where a built-in PEP already evaluates the Decision and dispatches in the same request,
with no meaningful time gap between them, the marginal security benefit of also performing this check
is small relative to a PEP acting on a portable Decision artifact fetched at an earlier, unbounded
time — but it remains available at near-zero marginal cost (the checks in §3 are targeted lookups and
claim reads, not chain re-verification), and an implementation MAY perform it on every dispatch path
uniformly for consistency and defense-in-depth rather than only where the time gap is largest.

On **approved execution** (§3.5) a gateway MUST perform this check, MUST record `request_binding` on
every decision it makes, and MUST make exactly one upstream request per claim: no transport-level
retries, and redirects are not followed (an upstream redirect response is returned to the caller as
the upstream's response). Any test or diagnostic mechanism that forwards a call despite a blocking
decision MUST NOT be honoured on this path.

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

Approved execution (§3.5) is the one case in which a stored Decision leads to a dispatch on a
re-presented call. It is not bearer use of the Decision: what `REVIEW_REQUIRED` waits for (Spec 00 §4) —
a human approval, or an explicitly configured policy continuation, distinguished as such — is
evidenced by a signed attestation, the call is bound byte-for-byte to the
reviewed call, the Authorities are revalidated, and the approval is consumed by at most one dispatch
within a signed window. Spec 00 KERNEL-NEG-02 states this exception explicitly; it requires every
control of §3.5 and never makes a stored `ALLOW` usable as bearer authority.

### 8.3 No new attack surface

The checks in §3.1–3.3 are read-only and reuse mechanisms Spec 05 (revocation) and the kernel
Authority object (expiry) already define, and introduce no new trust anchors or signing keys.
Approved execution (§3.5) adds two write paths — per-Decision binding salts and execution claims —
and one signed field (`execution_not_after`, Spec 07 §11.4). It introduces no new trust anchor or
signing key.

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
- Does not have the PEP store and replay reviewed calls, approve a modified call, permit more than
  one dispatch per approved Decision, or define approver-held keys or cross-organisation approvals —
  see §3.5.
- Does not define an equivalence rule for substituting MCP sessions — see §3.5.2.

## 10. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-08-13 | Initial public working draft, per RFC 0000-execution-time-authorization-validation |
| 0.1.1 | 2026-08-25 | §3-6 has a reference implementation, reachable directly and via at least one client SDK. |
| 0.2.0 | 2026-09-30 | §4: Execution Validation Records are signed (Spec 07 §11.6); signing-failure behaviour and the executed-after-failed-validation rule referenced |
| 0.3.0 | 2026-10-01 | §3.5 approved execution of `REVIEW_REQUIRED` Decisions: same-Decision model; byte-exact binding document for HTTP/MCP/A2A/direct with every forwarded header bound and no session substitution; salted `request_binding` (Spec 07 §11.2 text-field input over the 43-character `binding_sha256`) with vectors; eligibility from signed records only, attestation 1.1 required; expiry checked through the pre-dispatch stage; 5-second validation-to-dispatch limit; one dispatch attempt per Decision with atomic claim and uncertain-commit handling; failure table; direct-caller limits; human approval distinguished from policy continuation; payloads bound as uninterpreted bytes. §3, §4, §5, §6, §8.2, §8.3, §9 updated |
