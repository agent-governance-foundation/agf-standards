# Specification 10: API Protocol

**Version:** 0.7.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.4.1  
**Layer:** Core format  

## 1. Introduction

This specification defines the API protocol for all Agent Governance services: request/response formats, error codes, authentication, and versioning.

The service decomposition shown in this document (separate registry, trust, and policy-decision services) is illustrative. A conformant implementation MAY expose the same API surface from a single service or any other internal decomposition, provided the request/response behavior specified here is preserved.

## 2. Common Conventions

### 2.1 Base URL

```
https://{service}.{domain}.com/v1/
```

Example services:
- `registry.agf.acme.com` — Identity Registry
- `trust.agf.acme.com` — Trust Evaluator
- `pdp.agf.acme.com` — Policy Decision Point

### 2.2 Content Type

All requests and responses use `application/json`.

### 2.3 Versioning

- API version in URL path: `/v1/...`
- Breaking changes require a new version: `/v2/...`

## 3. Common Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes | `application/json` |
| `Accept` | Yes | `application/json` |
| `Authorization` | For auth | Bearer token (future) |
| `X-Request-ID` | Recommended | For tracing |
| `X-Client-Version` | Recommended | Client SDK version |

## 4. Common Response Format

### 4.1 Success (2xx)

```json
{
  "data": {...},
  "meta": {
    "request_id": "req_abc123",
    "timestamp": 1735603300
  }
}
```

### 4.2 Error (4xx, 5xx)

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Delegation chain has invalid signature at index 1",
    "details": {
      "invalid_index": 1,
      "invalid_token": "eyJ0eXAi..."
    },
    "request_id": "req_abc123"
  }
}
```

A client integrating against this single error envelope should also expect two framework-level exceptions to this shape: request-validation failures and rate-limit-exceeded responses commonly use their own framework's default error shape rather than this envelope, unless explicitly normalized.

### 4.3 Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_REQUEST` | 400 | Malformed request |
| `INVALID_SIGNATURE` | 400 | Signature verification failed |
| `EXPIRED` | 400 | Token expired |
| `REVOKED` | 400 | Delegation revoked |
| `CHAIN_BROKEN` | 400 | Delegation chain discontinuity |
| `SCOPE_INSUFFICIENT` | 403 | Scope doesn't cover action |
| `NOT_FOUND` | 404 | Resource not found |
| `REVOCATION_LIST_FAILED` | 500 | Could not fetch revocation list |
| `INTERNAL_ERROR` | 500 | Unexpected error |
| `APPROVAL_NOT_ESTABLISHED` | 403 | Approved execution: no verified approval request record and 1.1 approval attestation for the named approval (Spec 30 §3.5.4) |
| `APPROVAL_NOT_GRANTED` | 403 | Approved execution: the attested outcome is not a grant (Spec 30 §3.5.4) |
| `APPROVAL_EXPIRED` | 403 | Approved execution: past the signed `execution_not_after` (Spec 30 §3.5.5) |
| `APPROVAL_NOT_BINDABLE` | 403 | Approved execution: the Decision has no request binding, or its salt is missing or erased (Spec 30 §3.5.3) |
| `APPROVAL_CALLER_MISMATCH` | 403 | Approved execution: caller or organisation differs from the reviewed request (Spec 30 §3.5.4) |
| `APPROVAL_REQUEST_MISMATCH` | 409 | Approved execution: the re-presented call does not match the reviewed call (Spec 30 §3.5.2) |
| `APPROVAL_CONSUMED` | 409 | Approved execution: the Decision already has an execution claim (Spec 30 §3.5.6) |
| `APPROVAL_CLAIM_UNCERTAIN` | 503 | Approved execution: the claim's commit result is unknown; nothing was dispatched (Spec 30 §3.5.6) |
| `EXECUTION_EVIDENCE_UNAVAILABLE` | 503 | Approved execution: the Execution Validation Record could not be persisted and signed; nothing was claimed or dispatched (Spec 30 §3.5.5) |
| `EXECUTION_VALIDATION_STALE` | 503 | Approved execution: more than 5 seconds since validation (Spec 30 §3.5.5) |
| `POLICY_POINTER_CHANGED` | 409 | Policy change: the selection slot's version differs from the version the request expected, or a create found the slot already exists (Spec 06 §6.6.4). Nothing was changed |
| `POLICY_OPERATION_ID_REUSED` | 409 | Policy change: the operation identifier is already recorded for a request that differs in slot, operation, expected version, target revision or selection metadata (Spec 06 §6.6.4). Nothing was changed |
| `POLICY_IN_USE` | 409 | Policy deletion: a selection slot still selects one of the policy's revisions (Spec 06 §6.6.2). Nothing was changed |
| `POLICY_ACTIVATION_UNCERTAIN` | 503 | Policy change: the outcome of this request is not known: the commit result was lost, or a database failure other than a lock timeout occurred while obtaining the organisation's mutual exclusion. The change MUST NOT be assumed applied or not applied (Spec 06 §6.6.4) |
| `POLICY_LOCK_TIMEOUT` | 503 | Policy change, policy deletion, or a change of a policy's selection eligibility: the organisation's mutual exclusion was not obtained in time. **This request** applied and wrote nothing. It does **not** establish the outcome of an **earlier** request with the same operation identifier, which may still hold the mutual exclusion and commit (Spec 06 §6.6.4) |
| `FEDERATION_PEERING_LOCK_TIMEOUT` | 503 | Peering operation or federation selection change: the peering's mutual exclusion was not obtained in time. This request applied and wrote nothing |
| `FEDERATION_LIFECYCLE_LOCK_TIMEOUT` | 503 | Operation that changes an organisation's peerings, or a billing event that does: the organisation's peering-lifecycle mutual exclusion was not obtained in time. This request applied and wrote nothing |
| `POLICY_ENGINE_UNAVAILABLE` | 503 | Policy change: the selected revision could not be loaded and verified in the policy engine before the change (Spec 06 §6.6.4 item 5). Nothing was changed |
| `POLICY_SLOT_EMPTY` | 409 | Policy change: the slot to clear is already in the "not configured" state (Spec 06 §6.6.4 item 2). Nothing was changed |
| `POLICY_REVISION_NOT_FOUND` | 404 | Policy change: the policy has no accepted revision in the requesting organisation (Spec 06 §6.6.2) |
| `POLICY_REFERENCE_NOT_ALLOWED` | 422 | Policy creation: the policy references data outside its own namespace (Spec 06 §6.6.1 item 3). Nothing was stored |
| `POLICY_BUILTIN_NOT_ALLOWED` | 422 | Policy creation: the policy uses a built-in function outside the allowlist (Spec 06 §6.6.1 item 4). Nothing was stored |
| `POLICY_ENGINE_NOT_READY` | 503 | Decision request: the PDP is not ready to make authorization decisions (Spec 06 §6.7.3 item 1). **No decision was made**, so nothing may be dispatched on this response. The caller MAY repeat the **decision request** later, honouring `Retry-After` when present; it is never a reason to dispatch, or to repeat, the action itself |
| `POLICY_EVALUATION_EXPIRED` | 503 | Policy backtest: the run exceeded the bounded lifetime of its transient evaluation and stopped (Spec 06 §3.3.1, informative note). No Decision is affected; narrow the replayed range and retry |
| `POLICY_CHANGES_SUSPENDED` | 409 | Policy write: the operator has suspended policy writes for this deployment (an operator-imposed suspension, not a conflict with another change). Nothing was changed or recorded |
| `IDENTITY_NAME_TAKEN` | 409 | Agent registration: the DID is reserved (the platform DID, or the organisation-identity form) or already names a registered identity of any kind (Spec 08 §3.4). Nothing was registered. Organisation registration reports the same condition with `REGISTRY_SLUG_OR_DID_ALREADY_TAKEN` |
| `POLICY_NOT_FOUND` | 404 | Policy request: the policy does not exist in the caller's organisation. Nothing was changed |
| `POLICY_NOT_MERGED` | 409 | Policy change: the policy has a review workflow and is not merged. Checked before the operation identifier is resolved (see §4.4). Nothing was changed |
| `POLICY_APPROVAL_REQUIRED` | 409 | Policy change: the organisation requires approval and the policy is not approved. Checked before the operation identifier is resolved (see §4.4). Nothing was changed |
| `CANARY_PERCENTAGE_OUT_OF_RANGE` | 400 | Canary: the percentage is not between 1 and 99. Nothing was changed |
| `CANARY_POLICY_ALREADY_ACTIVE` | 400 | Canary: the policy is the active policy. Nothing was changed |
| `POLICY_NO_ACTIVE_POLICY` | 409 | Roll back: no policy is active. Checked after the operation identifier is resolved (see §4.4). Nothing was changed |
| `POLICY_NO_ROLLBACK_TARGET` | 409 | Roll back: no earlier policy to return to. Checked after the operation identifier is resolved. Nothing was changed |
| `POLICY_ROLLBACK_TARGET_NOT_ELIGIBLE` | 409 | Roll back: the earlier policy is not merged, or not approved where approval is required. Checked after the operation identifier is resolved. Nothing was changed |

### 4.4 Retrying Policy Changes

A policy change (activate, roll back, start or change a canary, stop a canary, attach, detach) carries a caller-chosen operation identifier and the slot version the caller read (Spec 06 §6.6.4). The error codes above mean the following for a retry:

| Code | Retry? | What the caller does |
|---|---|---|
| `POLICY_ACTIVATION_UNCERTAIN` (503) | **Yes, unchanged** | Repeat the request with the **same** operation identifier and an **identical** request: slot, operation, expected version, target revision and selection metadata. The PDP resolves the retry under the organisation's mutual exclusion: if the original committed, it returns that recorded outcome; if not, it applies the request at most once. Clients SHOULD back off between retries (for example exponentially, with jitter) and SHOULD honour a `Retry-After` header when present. A retry whose own outcome is unknown returns `POLICY_ACTIVATION_UNCERTAIN` again, or `POLICY_LOCK_TIMEOUT` if it could not obtain the mutual exclusion; neither reports the change as applied or not applied. |
| `POLICY_LOCK_TIMEOUT` (503) | **Yes, unchanged** | This request changed nothing, but an earlier request with the same operation identifier may still commit. Repeat the **identical** request with the **same** operation identifier, backing off between retries, until it returns the recorded outcome or a definite answer. Do not start a different change for the same slot meanwhile. |
| `FEDERATION_PEERING_LOCK_TIMEOUT`, `FEDERATION_LIFECYCLE_LOCK_TIMEOUT` (503) | **Yes, unchanged** | Nothing was applied. Repeat the identical request (for a federation selection change, with the same operation identifier), backing off between retries. |
| `POLICY_POINTER_CHANGED` (409) | **No, not unchanged** | Another change won. Re-read the slot, decide whether the intended change still applies, and if so submit it as a **new** operation, with a **new** operation identifier and the newly read version. |
| `POLICY_OPERATION_ID_REUSED` (409) | **No** | The identifier belongs to a different recorded request. Reusing it can never succeed. A genuinely new operation needs a new identifier. |
| `POLICY_ENGINE_UNAVAILABLE` (503) | **Yes** | Nothing changed. Retry later; the same operation identifier and identical request, or a new operation. |
| `POLICY_SLOT_EMPTY` (409) | **No** | The slot is already cleared; there is nothing to change. |
| `POLICY_IN_USE` (409) | **Not until resolved** | Clear or re-point every slot that selects the policy's revisions (each such change is itself a policy change), then retry the deletion. |
| `POLICY_CHANGES_SUSPENDED` (409) | **No** | Policy writes are suspended by the operator. Automatic retry is inappropriate while suspension remains active. After the operator lifts the suspension, re-read the slot and submit the change as a **new** operation, with a **new** operation identifier and the newly read version. |

**Refusals and retries.** A refusal checked **before** the operation identifier is resolved (`POLICY_NOT_FOUND`, `POLICY_NOT_MERGED`, `POLICY_APPROVAL_REQUIRED`, `CANARY_PERCENTAGE_OUT_OF_RANGE`, `CANARY_POLICY_ALREADY_ACTIVE`, and the request's own validation) establishes only that **this request** was refused. It is a definite answer for the first request of an operation. For a retry it is not: an earlier request with the same operation identifier may still commit, having passed those checks when it was made. A client retrying an uncertain change MUST NOT treat such a refusal as the outcome of the earlier request. A refusal checked **after** the identifier is resolved under the organisation's mutual exclusion (`POLICY_NO_ACTIVE_POLICY`, `POLICY_NO_ROLLBACK_TARGET`, `POLICY_ROLLBACK_TARGET_NOT_ELIGIBLE`, `POLICY_POINTER_CHANGED`) is a definite answer for any request: the operation is not recorded, and nothing was changed. A code a client does not recognise establishes nothing about the outcome.

A success response to a retried request reports the outcome recorded for the original operation, including the resulting slot version. A client MUST NOT treat the slot's current contents as evidence that its own operation succeeded.

## 5. Service APIs

### 5.1 Identity Registry API

**`POST /v1/identities`** — Register a new agent identity

Request:

```json
{
  "controller": "did:agf:acme:service:it",
  "verification_method": {
    "type": "JsonWebKey2020",
    "publicKeyJwk": {...}
  },
  "services": []
}
```

Response:

```json
{
  "data": {
    "did": "did:agf:acme:agent:new-01",
    "document": {...},
    "created_at": 1735603200
  }
}
```

**`GET /v1/identities/{did}`** — Resolve DID to document. Response: DID document.

**`GET /v1/identities?controller={did}`** — List identities by controller

Response:

```json
{
  "data": ["did:...", "did:..."],
  "meta": {"page": 1, "total": 42}
}
```

### 5.2 Trust Evaluator API

**`POST /v1/evaluate`** — Evaluate a delegation chain

Request:

```json
{
  "chain": ["jwt_1", "jwt_2", "jwt_3"],
  "action": {
    "type": "read:calendar",
    "resource": "calendars/alice@acme.com"
  },
  "context": {
    "timestamp": 1735603300,
    "source_ip": "10.0.1.45"
  },
  "revocation_list_url": "https://acme.com/revocations.json"
}
```

Response:

```json
{
  "data": {
    "trust_score": 82,
    "decision": "ALLOW",
    "penalties": {
      "depth": {"hops": 3, "penalty": -10},
      "age_hours": {"value": 4, "penalty": -8}
    },
    "lineage_depth": 3,
    "revoked": false,
    "expired": false
  }
}
```

### 5.3 Risk Evaluator API

**`POST /v1/risk`** — Calculate risk score

Request:

```json
{
  "action": {"type": "approve:payment", "resource": "amount=150000"},
  "context": {
    "timestamp": 1735603300,
    "source_ip": "203.0.113.0",
    "velocity": 10
  },
  "trust_score": 73
}
```

Response:

```json
{
  "data": {
    "inherent_risk": 85,
    "environmental_risk": 35,
    "trust_weight": 0.73,
    "final_risk": 110,
    "decision": "DENY"
  }
}
```

### 5.4 Policy Engine API

**`POST /v1/evaluate`** — Evaluate policy

Request:

```json
{
  "policy_version": "acme/policies/calendar/access@1.2.0",
  "input": {
    "action": {"type": "read:calendar"},
    "subject": "did:example:agent:abc",
    "trust_score": 82
  }
}
```

Response:

```json
{
  "data": {
    "allow": true,
    "allow_with_caution": false,
    "deny": false,
    "reason": ["valid_chain", "risk_acceptable"],
    "policy_hash": "sha256:abc123..."
  }
}
```

### 5.5 PDP API

**`POST /v1/decide`** — Final authorization decision

Request:

```json
{
  "chain": ["jwt_1", "jwt_2", "jwt_3"],
  "action": {"type": "read:calendar", "resource": "..."},
  "context": {
    "timestamp": 1735603300,
    "source_ip": "10.0.1.45"
  }
}
```

Optional request field `policy_version` (string): a pin (Spec 06 §6.5).
- It is honoured only when the caller's credential carries the organisation permission `policies.pin`. Otherwise the decision is `DENY` with `error_code: POLICY_VERSION_UNAUTHORIZED`.
- It cannot replace a pin carried by the delegation chain. If the chain carries an authorized pin and the body names a different version, the decision is `DENY` with `error_code: POLICY_VERSION_CONFLICT` (Spec 06 §6.5).
- A pin is evaluated in addition to the organisation's policy. It never disables or replaces it.

Response:

```json
{
  "data": {
    "decision": "ALLOW",
    "trust_score": 82,
    "risk_score": 45,
    "policy_version": "acme/policies/calendar/access@1.2.0",
    "artifact_id": "dec_1735603300_a1b2c3"
  }
}
```

`decision` is one of `ALLOW`, `ALLOW_WITH_CAUTION`, `DENY`, `REVIEW_REQUIRED`. `REVIEW_REQUIRED` means the action must not proceed until a human judgment is rendered (Spec 15); the kernel mapping for all four values is defined in Spec 00 §4.2.

When the request body or a token's `policy_version` claim names a policy version (a pin, Spec 06 §6.5), the response additionally carries:

| Field | Type | Description |
|-------|------|-------------|
| `policy_version_requested` | string | The version that was asked for |
| `policy_version_applied` | string or null | The pinned version evaluated in addition to the organisation's policy — `null` when the pin was not applied |
| `error_code` | string | Present when the pin was not applied: `POLICY_VERSION_NOT_FOUND` (the version does not exist for the requesting organisation; a version of another organisation is reported identically), `POLICY_VERSION_UNAUTHORIZED` (the pin is not authorized) or `POLICY_VERSION_CONFLICT` (the body names a version different from the delegation chain's authorized pin) |

These fields are present only when the pin outcome was determined (Spec 06 §6.5). A decision that ended earlier, for example on an invalid or revoked delegation chain, carries its own `error_code` and none of these fields.

These codes are decision outcomes in the decision response, not HTTP errors (§4.3).
- `POLICY_VERSION_UNAUTHORIZED` or `POLICY_VERSION_CONFLICT`: the decision is `DENY`.
- `POLICY_VERSION_NOT_FOUND` where the organisation has a policy that applies to the request: the decision is `DENY`.
- `POLICY_VERSION_NOT_FOUND` where no organisation policy applies (the pin was authorized): the request is decided on trust and risk alone, and the decision is capped at `ALLOW_WITH_CAUTION`.

The legacy `policy_version` field is unchanged for compatibility; new consumers SHOULD read `policy_version_applied`.

**Policy required** (Spec 06 §6.7.1). When the organisation requires an active policy and has none for the request, the decision is `DENY` with `error_code: POLICY_REQUIRED`, a decision outcome, not an HTTP error. It is final: no approval or emergency override applies. The response carries a single `error_code`: when a pin outcome was also determined, `error_code` is `POLICY_REQUIRED`, the condition that decided the outcome. The pin stays visible in `policy_version_requested` and `policy_version_applied: null`, and its own outcome is in the signed policy block (`pin_status`, Spec 07 §3.3).

**Issuer, identity and federation denials.** The codes below are decision outcomes, not HTTP errors (§4.3):
- the decision is `DENY`;
- the code is the response's `error_code`, and is also recorded as a `reasoning` entry;
- no pin fields are present unless a pin outcome was determined before the denial.

For a root issuer owned by another organisation, the federation checks run in the order shown (Spec 26 §2.1 item 3), and the first applicable code is reported.

| Code | Trigger | Source |
|------|---------|--------|
| `federation_chain_malformed` | A token cannot be decoded, or its `iss` is missing or not a string | Spec 26 §2.1 item 2 |
| `federation_precheck_unavailable` | The organisation registry or the peering could not be read | Spec 26 §2.1 item 2 |
| `identity_unavailable` | An issuer identity could not be looked up | Spec 02 §3.10, Spec 08 §3.4 |
| `identity_not_found` | An issuer identity is not registered (every environment) | Spec 02 §3.10, Spec 08 §3.4 |
| `issuer_key_unbound` | The key that actually verified a token is not a registered key of that token's `iss` identity | Spec 01 §3.1, Spec 02 §3.4 |
| `caller_org_not_registered` | 1st federation check: the root's issuer is owned by another organisation, and the requesting organisation has no organisation-registry entry | Spec 26 §2.1 item 3 |
| `issuer_org_not_in_registry` | 2nd federation check: the organisation owning the root's issuer is unknown or inactive in the registry | Spec 26 §2.1 item 3 |
| `no_active_federation_trust` | 3rd federation check: no active peering between the requesting organisation and the root's owner | Spec 26 §2.1 items 1, 3 |
| `issuer_not_trusted` | A token's issuer is outside the set permitted by the chain's root: a non-requester issuer under a requester-owned or platform root; an issuer owned by neither the requester nor the root's peer under a foreign root; or a platform root whose subject the requester does not own | Spec 02 §3.10 |

A refusal to issue a Trust Summary (`POST /v1/delegations/summarize`) for the same reasons reports the same codes in the same `DENY` shape, and no summary is signed (Spec 24 §5).

### 5.6 Audit Service API

**`GET /v1/artifacts/{artifact_id}`** — Retrieve decision artifact. Response: Decision artifact (see Spec 07).

**`GET /v1/artifacts`** — Search artifacts

Query params:
- `start_time` (Unix timestamp)
- `end_time` (Unix timestamp)
- `decision` (`ALLOW`, `ALLOW_WITH_CAUTION`, `DENY`, `REVIEW_REQUIRED`)
- `subject` (DID)
- `verifier` (DID)
- `policy_version` (string)

**`POST /v1/artifacts/verify`** — Verify artifact signature

Request: `{"artifact": {...}}`  
Response: `{"valid": true, "signer": "did:..."}`

The verify response is two-stage — `signature_valid`, `semantic_valid`, and a structured `violations` array — per Spec 07 §6.3.1; the legacy `valid` field keeps its signature-only meaning.

**`GET /v1/receipts/{receipt_id}`** — Retrieve an Execution Receipt (see Spec 07 §10)

**`GET /v1/receipts?decision_ref={artifact_id}`** — All receipts correlated to a Decision artifact

### 5.7 Health Check API

**`GET /health`** — Service health

Response:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 3600,
  "checks": {
    "database": "ok",
    "revocation_cache": "ok"
  }
}
```

## 6. Rate Limiting

In a single-monolith deployment, a default rate-limit policy applies per-route rather than per-service, with specific routes overriding the default where needed — there's no per-service tier because there's no per-service deployment to tier. Operators should note: if rate-limit state is stored in-process rather than in a shared store, limits are enforced per-process, not cluster-wide — with N workers, the effective limit is the configured limit × N.

| Service | Default Limit | Burst |
|---------|---------------|-------|
| Identity Registry | 100/min | 200 |
| Trust Evaluator | 1000/min | 2000 |
| Risk Evaluator | 1000/min | 2000 |
| Policy Engine | 500/min | 1000 |
| PDP | 1000/min | 2000 |
| Audit Service | 100/min | 200 |

Rate limit headers:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1735603600
```

## 7. Authentication (Future)

For MVP, services are internal and authentication is optional.

For production:
- Service-to-service: mTLS
- Client-to-service: Bearer token (OAuth2)
- Admin operations: Strong authentication (MFA)

## 8. Example: Complete Decision Flow

Request:

```bash
curl -X POST https://pdp.acme.com/v1/decide \
  -H "Content-Type: application/json" \
  -d '{
    "chain": ["eyJ0eXAi...", "eyJ0eXAi..."],
    "action": {"type": "read:calendar"},
    "context": {"timestamp": 1735603300}
  }'
```

Response:

```json
{
  "data": {
    "decision": "ALLOW",
    "trust_score": 82,
    "risk_score": 45,
    "artifact_id": "dec_1735603300_a1b2c3"
  },
  "meta": {
    "request_id": "req_1735603300_xyz",
    "timestamp": 1735603301
  }
}
```

## 9. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
| 0.2.0 | 2026-07-14 | Documented the complete four-value `decision` enum (added missing `REVIEW_REQUIRED`) in §5.5 and the artifact-search filter, with kernel mapping reference (Spec 00 §4.2) |
| 0.3.0 | 2026-07-14 | §5.5: added `policy_version_requested` / `policy_version_applied` / `error_code: POLICY_VERSION_NOT_FOUND` response fields for the missing-policy-version state (Spec 06 §6.5, KERNEL-NEG-03) |
| 0.4.0 | 2026-07-15 | §5.6: Execution Receipt endpoints and two-stage verify response (Spec 07 §10, §6.3.1) |
| 0.4.1 | 2026-10-01 | §4.3: approved-execution error codes (Spec 30 §3.5) |
| 0.5.0 | 2026-10-05 | §4.3: policy-change error codes `POLICY_POINTER_CHANGED` (409), `POLICY_OPERATION_ID_REUSED` (409), `POLICY_IN_USE` (409) and `POLICY_ACTIVATION_UNCERTAIN` (503) (Spec 06 §6.6). Added §4.4 Retrying Policy Changes: an uncertain change is retried with the same operation identifier and an identical request, and resolved by the recorded outcome; conflicts and reused identifiers are not retried unchanged. §4.3 adds `POLICY_CHANGES_SUSPENDED` (409, an operator-imposed suspension of policy writes; not retried automatically while the suspension is active). §5.5: the body `policy_version` is a pin requiring the `policies.pin` permission; `POLICY_VERSION_UNAUTHORIZED` and `POLICY_VERSION_CONFLICT` (a body pin cannot replace an authorized chain pin); a pin that is not found, unauthorized or in conflict is `DENY` where an organisation policy applies, and the `ALLOW_WITH_CAUTION` cap remains only for an authorized pin with no organisation policy (Spec 06 §6.5) Corrected 2026-10-06: a missing comma in the §5.5 `error_code` row. Amended (2026-10-07, draft): §4.3 adds `POLICY_ENGINE_NOT_READY`, `POLICY_ENGINE_UNAVAILABLE`, `POLICY_SLOT_EMPTY`, `POLICY_REVISION_NOT_FOUND`, `POLICY_EVALUATION_EXPIRED`, `POLICY_REFERENCE_NOT_ALLOWED`, `POLICY_BUILTIN_NOT_ALLOWED`; §4.4 retry rules for two of them. Clarified (2026-10-07, draft): §5.5 pin response fields only when the pin outcome was determined. Federation selection and issuer trust (2026-10-08, draft): §5.5 issuer, identity and federation denials are decision outcomes reported in `error_code` and as a `reasoning` entry, with triggers: `federation_chain_malformed`, `federation_precheck_unavailable`, `identity_unavailable`, `identity_not_found`, `issuer_key_unbound`, the ordered checks `caller_org_not_registered`, `issuer_org_not_in_registry`, `no_active_federation_trust`, and `issuer_not_trusted`; Trust Summary issuance refusals use the same codes |
| 0.6.0 | 2026-10-12 | §4.3: `POLICY_ACTIVATION_UNCERTAIN` describes the unknown outcome precisely (a lost commit result, or a database failure other than a lock timeout while obtaining the organisation's mutual exclusion); a lock timeout is now `POLICY_LOCK_TIMEOUT` (503: this request applied nothing; an earlier request with the same operation identifier may still commit). Added `FEDERATION_PEERING_LOCK_TIMEOUT` and `FEDERATION_LIFECYCLE_LOCK_TIMEOUT` (503, nothing applied). §4.4: retry rows for the three lock codes (identical request, same operation identifier) |
| 0.6.1 | 2026-10-13 | §4.3: policy-change refusal codes `POLICY_NOT_FOUND` (404), `POLICY_NOT_MERGED` and `POLICY_APPROVAL_REQUIRED` (409), `CANARY_PERCENTAGE_OUT_OF_RANGE` and `CANARY_POLICY_ALREADY_ACTIVE` (400), `POLICY_NO_ACTIVE_POLICY`, `POLICY_NO_ROLLBACK_TARGET` and `POLICY_ROLLBACK_TARGET_NOT_ELIGIBLE` (409), each stating whether it is checked before or after the operation identifier is resolved. §4.4: what such a refusal means for a retry (a before-resolution refusal is never the outcome of an earlier request). Identity names (2026-10-14, draft): §4.3 adds `IDENTITY_NAME_TAKEN` (409) |
| 0.7.0 | 2026-10-16 | RR-0017 (draft): §5.5 `POLICY_REQUIRED` (`DENY`, final) for an organisation that requires an active policy and has none; it is the response's single `error_code` when a pin outcome was also determined, with the pin kept in `policy_version_requested`/`policy_version_applied` and the signed policy block. |
