# Specification 13: Privacy and Selective Disclosure

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Profile  

## 1. Introduction

Audit artifacts and delegation chains may contain sensitive personal data (PII). This specification defines privacy-preserving techniques including selective disclosure, zero-knowledge proofs, and data minimization.

## 2. Privacy Principles

1. **Data minimization:** Only log what is necessary
2. **Purpose limitation:** Use data only for audit
3. **Storage limitation:** Delete or anonymize when no longer needed
4. **Integrity and confidentiality:** Protect artifacts from unauthorized access
5. **Accountability:** Document privacy practices

## 3. Selective Disclosure for Delegation Tokens

### 3.1 Problem

A delegation token may contain sensitive claims (e.g., `scope: ["read:payroll/ssn"]`) that the agent should not reveal to every verifier.

### 3.2 Solution: Bound Signatures

Use BBS+ signatures (or similar) to enable selective disclosure:

```json
{
  "iss": "did:agf:acme:alice",
  "sub": "did:agf:acme:agent:builder",
  "aud": "https://build.acme.com",
  "exp": 1735689600,
  "jti": "del_abc123",
  "revealed_claims": ["scope.read:source-code", "scope.run:build"],
  "hidden_claims_hash": "sha256:..."
}
```

The verifier only sees the revealed claims; hidden claims remain confidential but are cryptographically bound to the signature.

### 3.3 Interim Approach Pending Wide BBS+ Support

BBS+ signatures are not yet widely supported. For MVP, use:

- **Option A (default):** Full disclosure — simpler, less private
- **Option B:** Separate tokens per sensitivity level
- **Option C:** Encrypted claims with per-verifier keys

Future versions will standardize on BBS+.

## 4. Artifact Anonymization

### 4.1 Automatic Anonymization

Audit service MUST provide an anonymization endpoint:

```bash
POST /v1/artifacts/anonymize
{
  "artifact_id": "dec_1735603300_a1b2c3",
  "retention_period_days": 90
}
```

Response: anonymized artifact with PII removed or hashed.

### 4.2 Anonymization Rules

| Field Type | Action |
|------------|--------|
| Agent DID (subject) | Hash with stable salt |
| Source IP | Truncate to `/24` |
| Resource path | Remove after 3rd segment |
| Custom user data | Redact entirely |
| Timestamps | Keep (needed for audit) |
| Decision | Keep |
| Trust scores | Keep |

### 4.3 Example

Original:

```json
{
  "subject": "did:agf:acme:agent:alice-personal-01",
  "source_ip": "203.0.113.45",
  "resource": "calendars/alice@acme.com/private/event-123"
}
```

Anonymized:

```json
{
  "subject_hash": "sha256:salt+did...",
  "source_ip": "203.0.113.0/24",
  "resource": "calendars/alice@acme.com/..."
}
```

## 5. Data Minimization Guidelines

### 5.1 What NOT to Log

- User passwords or credentials
- Session tokens (except `jti` references)
- Full delegation chain content (log hashes instead)
- Internal system details (paths, versions)
- Unnecessary personal attributes

### 5.2 What TO Log

- Decision (allow/deny)
- Timestamp
- Subject DID (hashed for long-term storage)
- Action type
- Policy version
- Trust score components
- Revocation status

### 5.3 Delegation Chain Hashing

Instead of storing the full chain, store:

```json
{
  "chain_hash": "sha256:abc123...",
  "chain_length": 3,
  "root_issuer": "did:agf:acme:alice"
}
```

The full chain can be reconstructed from audit logs if needed (with appropriate access controls).

## 6. Access Controls for Audit Artifacts

### 6.1 Role-Based Access

| Role | Access |
|------|--------|
| Auditor (internal) | Read all artifacts, verify signatures |
| Security analyst | Read decisions; PII fields denied |
| Developer | Read own agent's artifacts only |
| Compliance officer | Full access with approval |
| Outsourced auditor | Limited read-only, sessions logged |

### 6.2 Access Logging

All access to audit artifacts MUST be logged:

```json
{
  "timestamp": 1735603300,
  "user": "did:agf:acme:auditor-bot",
  "action": "READ",
  "artifact_id": "dec_...",
  "reason": "annual_audit",
  "approved_by": "did:agf:acme:compliance-lead"
}
```

## 7. Cryptographic Erasure (GDPR Right to Delete)

### 7.1 Method

1. Encrypt each artifact with a unique data encryption key (DEK)
2. Store the DEK in a KMS or separate encrypted store
3. Map DEK to artifact ID in a mapping table
4. To delete: destroy the DEK (not the artifact itself)

### 7.2 Implementation

```python
# Artifact encryption
dek = generate_key()                       # unique per artifact
encrypted_artifact = encrypt(artifact, dek)
kms.store(artifact_id, dek)               # KMS or separate encrypted store

# Deletion (GDPR request)
kms.delete(artifact_id)                   # Key destroyed; artifact now inaccessible

# Verification
artifact = read_from_storage(artifact_id)  # Returns encrypted blob
decrypt(artifact, kms.get(artifact_id))   # Fails — key not found
```

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
