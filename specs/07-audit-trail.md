# Specification 07: Audit Trail and Decision Provenance

**Version:** 0.2.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.1  
**Layer:** Core format  

## 1. Introduction

Every trust decision must be auditable. This specification defines the decision artifact format, signing requirements, storage, and query interface.

## 2. Core Principle

**The decision artifact is self-contained proof.**

Auditors should not need access to the original system to verify a decision. The artifact contains everything needed: input, output, policies used, revocation state, and signatures.

## 3. Decision Artifact Format

### 3.1 Schema

```json
{
  "artifact_id": "dec_1735603300_a1b2c3d4",
  "schema_version": "1.1",
  "timestamp": 1735603300,
  "verifier_id": "https://pdp.acme.com",
  "agent_id": "did:example:agent:xyz",

  "request": {
    "delegation_chain": ["jwt_1", "jwt_2", "jwt_3"],
    "action": {
      "type": "read:calendar",
      "resource": "calendars/alice@acme.com"
    },
    "context": {
      "timestamp": 1735603300,
      "source_ip": "10.0.1.45",
      "request_id": "req_xyz"
    }
  },

  "response": {
    "decision": "ALLOW",
    "trust_score": 82,
    "risk_score": 45,
    "reasoning": ["valid_delegation_chain", "risk_below_threshold"],
    "penalties": {
      "depth": {"hops": 3, "penalty": -10},
      "age_hours": {"value": 4, "penalty": -8},
      "revoked": false,
      "expired": false,
      "scope_match": true,
      "signatures_valid": true
    }
  },

  "policy": {
    "version": "acme/policies/calendar/access@1.2.0",
    "decision": "ALLOW",
    "sha256": "abc123..."
  },

  "revocation_state": {
    "method": "live_db",
    "checked_at": 1735603300,
    "checked_jtis": ["del_7f3e9a2b"],
    "result": "passed"
  },

  "signatures": [
    {
      "signer": "did:example:pdp-01",
      "algorithm": "ES256",
      "signature": "base64...",
      "timestamp": 1735603301
    }
  ]
}
```

### 3.2 Field Definitions

| Field | Required | Description |
|-------|----------|-------------|
| `artifact_id` | Yes | Unique identifier |
| `schema_version` | Yes | Artifact schema version |
| `timestamp` | Yes | Decision time |
| `verifier_id` | Yes | DID of PDP |
| `agent_id` | Yes | Acting principal (chain leaf subject); `null` when unextractable. Part of the signed evidence payload, so the serialized document must carry it |
| `request` | Yes | Complete request |
| `response` | Yes | Complete response |
| `policy` | Yes | Policy version, decision, and content hash (`sha256`). When a requested policy version was not found, additionally carries `requested_version` and `used_version: null` (Spec 06 §6.5) |
| `revocation_state` | Yes | The revocation check the decision actually ran: `method` (`live_db` for a decide-time database check, `static_list` for a versioned list), `checked_at`, `checked_jtis`, and `result` (`passed` or `revoked:<jti>`). Empty when the chain was rejected before the revocation check ran |
| `signatures` | Yes | Signatures from verifier(s) |

## 4. Signing Requirements

### 4.1 Who Signs

- **Primary signer:** The PDP making the decision (MUST sign)
- **Optional signers:** Trust evaluator, policy engine (MAY sign for additional verification)

### 4.2 Signature Algorithm

- Algorithm: ES256 (ECDSA with P-256)
- Same as delegation tokens

A conformant implementation MUST NOT silently fall back to a weaker symmetric signing scheme (e.g. HMAC with a shared secret) when no asymmetric signing key is configured — a shared-secret signature cannot be independently verified by a third party who doesn't hold that secret, defeating §2's self-contained-proof principle. If a fallback path exists, the artifact's recorded signing algorithm MUST honestly reflect which algorithm was actually used.

One conformant approach is environment-gated enforcement: in production environments, startup fails outright when no ES256 key is loadable. Outside production, an HMAC-SHA256 fallback is permitted for development convenience, logged at ERROR level on every use, and recorded honestly as `"algorithm": "HMAC-SHA256"` in the signature block.

### 4.3 Signature Calculation

The signature covers a **named, closed evidence payload** — the fields that constitute the decision's evidence — rather than "the whole document minus `signatures`". This is deliberate: operational metadata added to the record later (trace IDs, latency, new top-level fields) must never be able to invalidate an existing signature just by being added.

The evidence payload is exactly:

```python
evidence_payload = {
    "artifact_id": artifact_id,
    "timestamp": timestamp,
    "agent_id": agent_id,
    "request": request,      # delegation chain, action, context
    "response": response,    # decision, scores, reasoning, override state
    "policy": policy,        # version, decision, content hash
}
payload_bytes = json.dumps(evidence_payload, separators=(",", ":"), sort_keys=True).encode()
signature = sign(payload_bytes, private_key)  # ES256 over the canonical bytes
```

Canonical encoding is JSON with sorted keys and compact separators. Excluded by design: `schema_version`, `verifier_id` (bound instead via the signature block's `signer`), `revocation_state`, and the `signatures` block itself.

Signing only a trivial subset of fields (e.g. just `artifact_id`, `decision`, `trust_score`, `timestamp`) remains a conformance violation: everything that evidences the decision — the delegation chain, resource, reasoning, policy — MUST be inside the signed payload, otherwise an attacker who can modify stored artifacts can alter them without invalidating the signature, undermining §9.1's tamper-detection guarantee and §2's self-contained-proof principle.

### 4.4 Signature Acceptance Rules

When an auditor (human, tool, or automated system) verifies a decision artifact, the following rules determine whether the artifact is considered valid:

**Required for any acceptance:**

The primary PDP signature MUST be present and valid. An artifact missing a PDP signature, or with an invalid PDP signature, MUST be rejected as unverifiable.

**Optional signer handling:**

- If an optional signer's signature is present but invalid, the artifact MUST be flagged with `signature_warning: true` and the anomaly logged, but the artifact SHOULD NOT be rejected on that basis alone (the PDP signature suffices for basic acceptance)
- If an optional signer's signature is absent, the artifact is still valid

**Conformance level requirements:**

| Conformance Level | Required Signatures |
|-------------------|---------------------|
| Level 1 | PDP (primary) |
| Level 2 | PDP + trust evaluator |
| Level 3 | PDP + trust evaluator + policy engine |

Implementations targeting Level 2 or 3 MUST ensure the additional services sign each artifact. Auditors verifying Level 2 or 3 artifacts MUST check all required signatures and reject artifacts where any required signature is missing or invalid.

## 5. Storage

### 5.1 Storage Backends

Reference implementation supports:

- Local filesystem (development)
- S3-compatible object storage (production)
- PostgreSQL (for querying)
- Immutable ledger (optional, for compliance)

### 5.2 Retention

| Use Case | Retention Period |
|----------|-----------------|
| Development | 30 days |
| Production | 90 days |
| Regulated (finance, healthcare) | 7 years |
| Government | Indefinite |

### 5.3 Storage Path (Filesystem)

```
audit-logs/
└── YYYY/
    └── MM/
        └── DD/
            └── {artifact_id}.json
```

In a multi-tenant deployment, an org segment MUST be added to this path (e.g. `decisions/{org_id}/{YYYY}/{MM}/{DD}/{artifact_id}.json`) to prevent one org's artifacts from colliding with another's.

## 6. Query Interface

### 6.1 API Endpoints

All routes are org-scoped: callers only see artifacts belonging to their own organization.

**`GET /v1/audit/{artifact_id}`** — Returns the artifact (including the full stored document)

**`GET /v1/audit?filter=...`** — Search artifacts with filters:
- `start_time`
- `end_time`
- `decision` (allow / deny / caution)
- `subject` (agent DID)
- `verifier`
- `policy_version`

**`POST /v1/audit/verify`** — Verifies artifact signatures

### 6.2 Query Example

```bash
curl "https://audit.acme.com/v1/audit?start_time=1735600000&decision=deny&subject=did:example:agent:xyz"
```

### 6.3 Signature Verification Endpoint

`POST /v1/audit/verify` accepts exactly one of:

- `artifact` — a full, self-contained artifact document (offline verification of a document presented by an auditor), or
- `artifact_id` — the id of an artifact stored by this PDP (org-scoped lookup).

The endpoint rebuilds the canonical evidence payload (§4.3) from the document and checks every entry in `signatures` against it — ES256 with the PDP's public key, HMAC-SHA256 with the shared secret. Artifacts with a `schema_version` older than the current one are reported invalid with an explanatory reason rather than being verified against the wrong payload layout.

```json
{
  "artifact_id": "dec_1735603300_a1b2c3d4",
  "schema_version": "1.1",
  "valid": true,
  "signatures": [
    {"signer": "https://pdp.acme.com", "algorithm": "ES256", "valid": true, "reason": null}
  ]
}
```

`valid` is true only when the artifact carries at least one signature and every signature verifies. Fully offline verification (§8.5) without this endpoint remains possible for auditors holding the PDP's public key, since the document carries every field of the evidence payload.

#### 6.3.1 Two-Stage Verification

Verification is two-stage: **cryptographic** (are the signatures valid?) and **semantic** (is the recorded history consistent?). The response carries both results; `valid` keeps its original signature-only meaning for compatibility:

```json
{
  "artifact_id": "dec_1735603300_a1b2c3d4",
  "schema_version": "1.1",
  "valid": true,
  "signature_valid": true,
  "semantic_valid": false,
  "violations": [
    {"code": "EXECUTED_AFTER_DENY", "detail": "receipt rcpt_1735603400_9f2e1c records execution of a denied action", "receipt_id": "rcpt_1735603400_9f2e1c"}
  ],
  "signatures": [
    {"signer": "https://pdp.acme.com", "algorithm": "ES256", "valid": true, "reason": null}
  ]
}
```

Semantic checks run only when the cryptographic stage passes, and cover the artifact together with any correlated Execution Receipts (§10):

| Code | Meaning |
|------|---------|
| `EXECUTED_AFTER_DENY` | A signature-valid Receipt records `outcome: executed` for a Decision whose `response.decision` is `DENY` (KERNEL-NEG-05, Spec 00 §6) |
| `EXECUTED_WITHOUT_APPROVAL` | As above for `REVIEW_REQUIRED` with no approved approval request linked to the Decision |
| `RECEIPT_WITHOUT_DECISION` | A Receipt references a `decision_ref` that does not resolve to a stored Decision artifact |
| `RECEIPT_SIGNATURE_INVALID` | A correlated Receipt's signature fails verification (does not affect the artifact's own `signature_valid`) |
| `POLICY_VERSION_MISMATCH` | The policy block records a requested-but-missing version (`used_version: null`) yet the response decision is an uncapped `ALLOW` — inconsistent with Spec 06 §6.5 |
| `PARENT_REVOKED` | A delegation in the decided chain was revoked **before** the decision timestamp. A revocation made after the decision is not a violation — validity is evaluated at decision time (Spec 00 §5) — and continues to surface only through `revocation_state` |

`semantic_valid` is true when no violations are found. A semantic violation never retroactively falsifies signatures; it means the signed evidence itself proves an enforcement or consistency failure.

## 7. Audit Requirements by Regulation

| Regulation | Requirement |
|------------|-------------|
| SOC 2 | Retention, access controls, integrity |
| ISO 27001 | Logging, monitoring, review |
| GDPR | Right to deletion — see Section 9.3 |
| HIPAA | 6-year retention, access logs |
| SOX | 7-year retention, immutable |

**GDPR compliance note:** Organizations subject to GDPR MUST implement cryptographic erasure (zeroization) of artifacts containing personal data after the retention period, not just deletion. Simple file deletion is insufficient.

**Cryptographic erasure method:**
1. Encrypt each artifact with a unique data key
2. Store the data key separately (e.g., in a KMS)
3. To "delete": destroy the data key, making the artifact permanently unreadable
4. The encrypted artifact may remain in storage but is cryptographically inaccessible

## 8. Example: Complete Audit Workflow

### 8.1 Request

Agent requests access to payroll.

### 8.2 PDP Decision

PDP evaluates and returns `ALLOW`.

### 8.3 Artifact Creation

PDP creates artifact with:
- Full request
- Full response
- Policy version used
- Revocation state
- PDP's signature

### 8.4 Storage

Artifact written to audit service.

### 8.5 Verification (6 months later)

Auditor queries artifact by ID:

1. Fetches artifact
2. Verifies signature (using PDP's public key)
3. Reviews request and decision
4. Confirms policy version was correct
5. Accepts decision as valid

## 9. Security Considerations

### 9.1 Tamper Detection

Signatures prevent undetected modification. If storage is compromised, signature verification fails.

### 9.2 Confidentiality

Artifacts may contain sensitive data (delegation chains, resources). Implement access controls on query API.

### 9.3 Privacy (GDPR)

For GDPR compliance, implement:

- **Artifact anonymization:** Remove or hash PII after retention period
- **Right to deletion:** Cryptographic erasure (see Section 7)
- **Data minimization:** Do not log unnecessary personal data
- **Access controls:** Restrict artifact access to authorized auditors only

## 10. Execution Receipts

A Decision artifact proves what was *permitted*. An **Execution Receipt** proves what *happened*: the signed record correlating a Decision to the attempted and actual outcome of the action. Receipts are the AGF serialization of the kernel Receipt object (Spec 00 §3.5).

### 10.1 Receipt Format

```json
{
  "receipt_id": "rcpt_1735603400_9f2e1c",
  "decision_ref": "dec_1735603300_a1b2c3d4",
  "attempted": true,
  "outcome": "executed",
  "upstream_status": 200,
  "gateway": "mcp",
  "completed_at": 1735603401,
  "signer": "https://gateway.acme.com",
  "algorithm": "ES256",
  "signature": "base64...",
  "signature_version": "1.0"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `receipt_id` | Yes | Unique identifier (`rcpt_` prefix, same convention as `artifact_id`) |
| `decision_ref` | Yes | `artifact_id` of exactly one Decision artifact |
| `attempted` | Yes | Whether execution was attempted after the Decision |
| `outcome` | Yes | `executed`, `not_executed`, or `unknown` — never inferred (Spec 00 §3.5) |
| `upstream_status` | No | Transport-level outcome evidence (e.g. HTTP status), outside the signed payload |
| `gateway` | Yes | The enforcement point that observed the outcome (`mcp`, `a2a`, `http`) |
| `completed_at` | Yes | When the outcome was recorded |
| `signer` | Yes | Identity of the enforcement point |
| `algorithm` / `signature` | Yes | Signature per §4.2's honesty rules |
| `signature_version` | Yes | Signed-payload layout version (currently `1.0`) |

### 10.2 Signing

The signature covers a named, closed payload — exactly `{receipt_id, decision_ref, attempted, outcome, completed_at, gateway, signature_version}` — canonically encoded as in §4.3 (sorted keys, compact separators). `upstream_status` and storage metadata are deliberately outside the signed payload: operational detail must never invalidate a receipt. §4.2's algorithm rules apply unchanged (ES256; any fallback recorded honestly).

### 10.3 Emission

Enforcement points that mediate execution (the protocol gateways, Specs 21–23) emit one Receipt per mediated decision:

| Situation | `attempted` | `outcome` |
|-----------|-------------|-----------|
| Decision `DENY`, call blocked | `false` | `not_executed` |
| Decision `REVIEW_REQUIRED` without approved approval, call blocked | `false` | `not_executed` |
| Call forwarded, upstream responded (any status) | `true` | `executed` |
| Call forwarded, timeout or transport error | `true` | `unknown` |

A blocked call's receipt is the affirmative evidence of enforcement — emitting receipts only for allowed calls proves nothing about denials. Receipt persistence MUST be best-effort with respect to the mediated call: a failure to record a receipt is logged and counted, and MUST NOT fail or delay the proxied request. Gateways expose the receipt via an `X-AGF-Receipt-ID` response header alongside `X-AGF-Artifact-ID`.

### 10.4 Lifecycle Rules

1. Every Receipt MUST reference exactly one Decision (`decision_ref`).
2. A Decision MAY have zero or more Receipts (retries, or multiple enforcement points).
3. A Receipt MUST NOT exist without a resolvable Decision — an orphan receipt is a `RECEIPT_WITHOUT_DECISION` violation (§6.3.1).
4. Receipts are evidence, not authority (Spec 00 §7.1): presenting a Receipt authorizes nothing.

### 10.5 Query Interface

- `GET /v1/receipts/{receipt_id}` — retrieve one receipt (org-scoped)
- `GET /v1/receipts?decision_ref={artifact_id}` — all receipts for a Decision

Receipt verification runs through `POST /v1/audit/verify` (§6.3.1), which checks receipt signatures and the receipt-vs-decision semantics together.

## 11. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
| 0.1.1 | 2026-07-14 | §3.2 `policy` field definition documents the conditional `requested_version`/`used_version` entries for the missing-policy-version state (Spec 06 §6.5) |
| 0.2.0 | 2026-07-15 | Added §10 Execution Receipts (kernel Receipt serialization: format, closed signed payload, gateway emission rules, lifecycle) and §6.3.1 two-stage verification with structured violation codes (EXECUTED_AFTER_DENY, EXECUTED_WITHOUT_APPROVAL, RECEIPT_WITHOUT_DECISION, RECEIPT_SIGNATURE_INVALID, POLICY_VERSION_MISMATCH, PARENT_REVOKED); Change Log renumbered §10→§11 |
