# Specification 07: Audit Trail and Decision Provenance

**Version:** 0.3.1 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.3.0  
**Layer:** Core format  

## 1. Introduction

Every trust decision must be auditable. This specification defines the decision artifact format, signing requirements, storage, and query interface.

## 2. Core Principle

**The decision artifact is self-contained proof.**

Auditors should not need access to the original system to verify a decision. The artifact contains everything needed: input, output, policies used, revocation state, and signatures.

What that proof covers — and what it does not — is bounded by Spec 00 §1.1.

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
      "kid": "NzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xs",
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

### 4.5 Key Publication and Selection

A signature is only independently verifiable if the verifier can obtain the signer's public key without privileged access to the signer's system (§2) — no account, credential, or operator cooperation. Retrieving the key set live still relies on TLS to the signer's origin at fetch time (see Locating the key set below). This section defines how ES256 signing keys are published and how a verifier selects the key for a given signature.

**Scope.** The key set covers every ES256 key a PDP signs with, whatever it signs — decision artifacts and Receipts, and any other PDP-signed object (for example decision records, trust summaries, override tokens, or delegation tokens the PDP issues under its own identity). One key typically signs several of these, so a rotation affects all of them at once, and every verifier of any of them selects keys by the rules below.

**Key identifier.** Every ES256 signature block — decision artifact `signatures[]` entries (§3.1) and Receipts (§10.1) — SHOULD carry `kid`: the RFC 7638 JWK SHA-256 thumbprint of the signing public key, base64url-encoded without padding. Because the thumbprint is computed from the key itself, a verifier holding any copy of the key can recompute and confirm it. `kid` is outside the signed payload (§4.3, §10.2): it is a selection hint, not evidence. An altered `kid` can make verification fail; it can never make an invalid signature verify, because the key it selects must come from the signer's published key set and the signature must still verify against that key. HMAC-SHA256 signatures carry no `kid` — a shared secret is never published (§4.2).

**Key set.** A PDP MUST publish its ES256 public keys as a JSON Web Key Set (RFC 7517) at `/.well-known/jwks.json`, served without authentication. Each key MUST include `kty`, `crv`, `x`, `y`, `kid`, `alg` (`"ES256"`), and `use` (`"sig"`), plus:

| Member | Required | Meaning |
|--------|----------|---------|
| `agf_status` | Yes | `active` (currently signing), `retired` (rotated out normally — signatures made while it was active remain valid), or `revoked` (compromised) |
| `agf_not_before` | No | Earliest time (Unix seconds) the key signed. Absent when unknown, e.g. a key already in use before key publication existed |
| `agf_not_after` | When not `active` | Time (Unix seconds) the key stopped being trusted for signing |

The key set MUST NOT contain private key material. A key MUST remain in the set for at least as long as artifacts it signed are retained (§5.2) — removing a key strands every artifact it signed. This is a deliberate exception to Spec 09 §5.2 step 6 (remove the old key after the grace period), which fits keys whose signed objects expire, such as delegation tokens, but not keys that sign retained evidence. Likewise, for evidence-signing keys this key set, not the DID document of Spec 09 §7.1, is the distribution mechanism a verifier relies on. On rotation, the previous key becomes `retired` with `agf_not_after` set to the rotation time; exactly one key SHOULD be `active` at a time. A key MUST NOT produce signatures after its `agf_not_after`, so a rotation procedure MUST ensure the previous key has stopped signing before the retirement time is recorded.

**Key-set integrity.** Changes to the key set — publishing a key, rotating, retiring, revoking — MUST be explicit, recorded operator actions (who and when). They MUST NOT happen as an implicit side effect of a PDP starting with a different signing key. A PDP whose loaded signing key is not the key set's `active` key MUST refuse to sign (fail closed) rather than sign with an unpublished key or alter the key set to match. As with §4.2's HMAC fallback, an implementation MAY automate key-set changes in non-production environments whose evidence is not relied on.

**Locating the key set.** When the signer identity (`signer`) is an HTTPS origin, the key set is at `{signer}/.well-known/jwks.json`. Otherwise the verifier obtains the key-set location out of band. Either way, the key set's authenticity rests on TLS to that origin at fetch time; a verifier checking evidence long after the fact SHOULD use a key-set snapshot captured with the evidence rather than assume the live endpoint is still reachable or unchanged.

**Signer identity changes.** A PDP's signer identity is stamped into every signature it has issued, so changing it must not strand earlier evidence. When a PDP changes its signer identity:

1. The key set at the new identity's origin MUST list every earlier signer identity in a top-level `agf_previous_signers` array.
2. Each earlier identity that is an HTTPS origin MUST keep serving `/.well-known/jwks.json` for as long as evidence naming it is retained — either the key set itself, or an HTTPS redirect to the new origin's key set.
3. A verifier fetches `{recorded signer}/.well-known/jwks.json` and follows **at most one** redirect. The redirect MUST be HTTPS and MUST point directly at `{successor origin}/.well-known/jwks.json`; a verifier refuses a non-HTTPS hop, a second redirect, or a redirect to any other path.
4. Origins are compared **exactly after normalization**: the RFC 6454 ASCII serialization (lowercase scheme and host, default port 443 omitted, no path, query, fragment, or trailing slash). No prefix, suffix, subdomain, or other loose URL matching. `agf_previous_signers` entries MUST be normalized origins.
5. The verifier accepts the key set it reaches only if either (a) no redirect occurred and the key set was served by the recorded signer's normalized origin, or (b) exactly one redirect occurred, it was served by the recorded signer's normalized origin, and the successor's key set lists that origin in `agf_previous_signers`.

The listing alone proves nothing: any origin could claim to succeed any other. The redirect alone is not enough either: the listing is what shows the new origin accepts the succession. **What this establishes is limited.** The redirect and the listing show that the two origins agree on the succession *at verification time*, each over its own TLS. They do not show who controlled either domain when an older artifact was signed. A verifier MUST report such a result as **live-origin verification** (direct, or via succession), never as historical attestation. A key-set snapshot captured with the evidence supports later verification, but historical attestation additionally requires independently authenticated evidence of the key set’s publication and time. If an earlier identity cannot be served (it is not an HTTPS origin, or its domain is no longer controlled), its evidence can only be verified with a key-set location obtained out of band, and the verifier MUST report the key-set provenance as out-of-band rather than as verified.

**Key selection.** For an ES256 signature, a verifier performs every step below; a key's presence in the key set, a matching `kid`, or a covering validity window never substitutes for verifying the signature.

1. **Candidates.** If `kid` is present, the only candidate is the key-set entry with that `kid`. If the key set has no such entry, the result is **unknown key**, reported distinctly from an invalid signature. If `kid` is absent — signatures issued before this section, or objects whose format has no key-set `kid` — the candidates are the non-revoked keys whose validity window covers the signature's timestamp. The timestamp only narrows the candidates; it never selects a key by itself. For objects whose `kid` is defined by another specification (such as a delegation token's DID-derived JOSE header `kid`, Spec 01), that `kid` is not a key-set identifier: the verifier treats it as absent and uses the object's issued-at time.
2. **Key-set entry check.** For each candidate, the verifier recomputes the RFC 7638 JWK SHA-256 thumbprint from the entry's public key members. If it does not equal the entry's `kid`, the entry is rejected and reported as **key-set mismatch**; it is never used.
3. **Cryptographic verification.** The verifier verifies the signature over the reconstructed signed payload (§4.3, §10.2) with the candidate's public key. With `kid` present, failure is **invalid signature**. Without `kid`, only a candidate whose key actually verifies the signature is selected; if none does, the result is **invalid signature**.
4. **Full validity window.** The signature's timestamp MUST NOT be before the selected key's `agf_not_before` (when present) and MUST NOT be after its `agf_not_after` (when present). Otherwise the result is **outside key validity**, even though the signature verified.
5. **Status.** A signature by a `revoked` key is never silently accepted. The signing timestamp is asserted by the signer, so a compromised key can backdate; such signatures are reported as **revoked key** regardless of timestamp, and any acceptance requires evidence outside the artifact.

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
  "execution_validation_ref": "xv_1735603400_7c2a91",
  "gateway": "mcp",
  "completed_at": 1735603401,
  "signer": "https://gateway.acme.com",
  "algorithm": "ES256",
  "kid": "NzbLsXh8uDCcd-6MNwXF4W_7noWXFZAfHkxZsRGC9Xs",
  "signature": "base64...",
  "signature_version": "1.1"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `receipt_id` | Yes | Unique identifier (`rcpt_` prefix, same convention as `artifact_id`) |
| `decision_ref` | Yes | `artifact_id` of exactly one Decision artifact |
| `attempted` | Yes | Whether execution was attempted after the Decision |
| `outcome` | Yes | `executed`, `not_executed`, or `unknown` — never inferred (Spec 00 §3.5) |
| `upstream_status` | No | Transport-level outcome evidence (e.g. HTTP status), outside the signed payload |
| `execution_validation_ref` | No | Id of the Spec 30 §4 Execution Validation Record checked immediately before this dispatch, if any (Spec 30 execution-time validation was performed). Absent when it wasn't. **Inside the signed payload as of `signature_version 1.1`** — see §10.2. |
| `gateway` | Yes | The enforcement point that observed the outcome (`mcp`, `a2a`, `http`) |
| `completed_at` | Yes | When the outcome was recorded |
| `signer` | Yes | Identity of the enforcement point |
| `algorithm` / `signature` | Yes | Signature per §4.2's honesty rules |
| `kid` | No | Key identifier per §4.5 (ES256 only). Outside the signed payload — a key-selection hint, not evidence |
| `signature_version` | Yes | Signed-payload layout version — `1.0` or `1.1` (§10.2) |

### 10.2 Signing

The signature covers a named, closed payload, canonically encoded as in §4.3 (sorted keys, compact separators). Which fields are in that payload depends on `signature_version`:

- **`signature_version: "1.0"`** — exactly `{receipt_id, decision_ref, attempted, outcome, completed_at, gateway, signature_version}`.
- **`signature_version: "1.1"`** — the same seven fields, plus `execution_validation_ref` (present and `null` when no execution-time check preceded this receipt, never omitted — the signed shape must not depend on whether the check ran). A verifier reconstructs the payload for the version the receipt actually declares; it must never assume every receipt is the latest version.

`1.0` receipts issued before `1.1` existed remain valid under the `1.0` shape — `signature_version` is not retroactively reinterpreted.

`kid` is outside the signed payload in both versions (§4.5). `upstream_status` and other storage metadata that is genuinely appended to the record after the fact stay outside the signed payload in both versions: operational detail added later must never invalidate a receipt. `execution_validation_ref` moved inside the signed payload in `1.1` specifically because it is always known before the receipt is built, not appended afterward — leaving a value that is known at build time outside the signature means it can be altered on the stored record without invalidating that record's own signature, which defeats its purpose as evidence correlating the receipt to the execution-time check that preceded it. §4.2's algorithm rules apply unchanged (ES256; any fallback recorded honestly).

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
| 0.3.0 | 2026-09-29 | Added §4.5 Key Publication and Selection: `kid` (RFC 7638 thumbprint) on ES256 signature blocks, outside the signed payload; unauthenticated JWKS at `/.well-known/jwks.json` with `agf_status`/`agf_not_before`/`agf_not_after` and retained retired keys; verifier key-selection rules — thumbprint recomputation, cryptographic verification with the selected key, full `agf_not_before`/`agf_not_after` window, revoked status; unknown key, key-set mismatch, invalid signature, outside key validity and revoked key reported distinctly; key set covers every PDP-signed object; key-set changes are explicit operator actions and a PDP fails closed on a key mismatch; explicit exception to Spec 09 §5.2 step 6 for evidence-signing keys; signer identity changes (`agf_previous_signers` plus a single HTTPS redirect from the earlier origin's key-set path, exact normalized-origin comparison, both required; reported as live-origin verification, not historical attestation). `kid` added to §3.1 and §10.1 examples, §10.1 field table, §10.2 |
| 0.3.1 | 2026-09-29 | §2: what the decision artifact proves is bounded by Spec 00 §1.1 (scope boundary) |
