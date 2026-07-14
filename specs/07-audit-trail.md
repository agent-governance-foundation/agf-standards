# Specification 07: Audit Trail and Decision Provenance

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None  
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
| `policy` | Yes | Policy version, decision, and content hash (`sha256`) |
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

## 10. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
