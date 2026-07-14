# Specification 09: Key Management and Rotation

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Core format  

## 1. Introduction

Cryptographic keys are the foundation of trust. This specification defines key generation, storage, rotation, and revocation requirements.

## 2. Key Types

### 2.1 Classification

| Key Type | Use | Sensitivity |
|----------|-----|-------------|
| Root signing | Sign trust anchors | CRITICAL |
| Domain signing | Sign domain delegations | HIGH |
| Agent signing | Sign agent delegations | MEDIUM |
| Verification | Verify signatures | LOW |
| TLS | Service communication | MEDIUM |

### 2.2 Algorithm Requirements

| Key Type | Algorithm | Key Size |
|----------|-----------|----------|
| All signing keys | ES256 (ECDSA P-256) | 256 bits |
| TLS keys | ECDHE with P-256 | 256 bits |

## 3. Key Generation

### 3.1 Generation Requirements

- MUST use cryptographically secure random number generator
- MUST NOT use predictable seeds
- SHOULD generate keys in hardware security module (HSM) for critical keys

### 3.2 Generation Command

```bash
# Generate private key
openssl ecparam -name prime256v1 -genkey -noout -out private-key.pem

# Extract public key
openssl ec -in private-key.pem -pubout -out public-key.pem
```

## 4. Key Storage

### 4.1 Storage Locations

| Key Type | Storage | Backup Required |
|----------|---------|-----------------|
| Root signing | HSM or air-gapped | Yes, encrypted |
| Domain signing | HSM or KMS | Yes, encrypted |
| Agent signing | Local filesystem (encrypted) | No |
| Verification | DID document | N/A |

### 4.2 Encryption at Rest

Private keys MUST be encrypted at rest:

```bash
# Encrypt private key
openssl enc -aes-256-gcm -salt -in private-key.pem -out private-key.enc
```

## 5. Key Rotation

### 5.1 Rotation Schedule

| Key Type | Rotation Frequency | Grace Period |
|----------|--------------------|--------------|
| Root signing | 365 days | 90 days |
| Domain signing | 180 days | 30 days |
| Agent signing | 90 days | 7 days |

### 5.2 Rotation Process

```
1. Generate new key pair
2. Add new verification method to DID document
3. Wait for propagation (2× cache TTL)
4. Start signing with new key
5. Continue accepting old key for verification (grace period)
6. After grace period, remove old key from DID document
7. Securely delete old private key
```

### 5.3 Rotation API

```bash
# Initiate rotation
POST /v1/identities/{did}/rotate
{
  "new_key": {...},
  "grace_period_seconds": 604800
}

# Complete rotation (after grace period)
POST /v1/identities/{did}/rotate/complete
```

## 6. Key Revocation

### 6.1 When to Revoke

- Key compromise suspected
- Employee/contractor departure
- Agent decommissioned
- Policy violation

### 6.2 Revocation Process

1. Remove verification method from DID document
2. Add key to global revocation list
3. Revoke all delegations signed with the key
4. Notify dependent systems

### 6.3 Emergency Revocation

For suspected compromise, immediate steps:

```bash
# Remove key from DID document
PUT /v1/identities/{did}/revoke-key/{key-id}

# Revoke all delegations from this issuer
POST /v1/revocations/bulk
{
  "issuer": "did:agf:acme:agent:compromised",
  "reason": "compromised"
}
```

## 7. Key Distribution

### 7.1 Public Key Distribution

Public keys are distributed via:
- DID documents (primary)
- Key servers (fallback)
- Trust anchors (for root keys)

### 7.2 Verification Key Caching

Verifiers SHOULD cache public keys with TTL:
- Default: 300 seconds
- Maximum: 3600 seconds

## 8. Hardware Security Modules

### 8.1 HSM Requirements

For critical keys (root, domain), HSMs MUST provide:
- FIPS 140-2 Level 3 or higher
- Key never leaves HSM
- Signed attestation of key generation

### 8.2 Supported HSMs

Reference implementation tested with:
- AWS CloudHSM
- HashiCorp Vault (HSM-backed)
- YubiHSM 2

## 9. Example: Full Key Lifecycle

### 9.1 Generation

```bash
./scripts/generate_agent_key.sh --agent-id "build-server-01" --output ./keys/
```

### 9.2 Registration

```bash
curl -X POST https://registry.acme.com/v1/identities \
  -d @did_document.json
```

### 9.3 Usage

```python
token = jwt.encode(payload, private_key, algorithm="ES256")
```

### 9.4 Rotation

```bash
./scripts/rotate_agent_key.sh --agent-id "build-server-01"
```

### 9.5 Revocation (Emergency)

```bash
./scripts/revoke_agent_key.sh --agent-id "build-server-01" --reason "compromised"
```

## 10. Security Considerations

### 10.1 Key Compromise

Assume keys will eventually be compromised. Design for rapid rotation and revocation.

### 10.2 Backup

Critical keys require encrypted backup:
- Backup MUST be encrypted with a separate key
- Backup key stored in a different location
- Access requires two-person rule

### 10.3 Auditing

All key operations (generation, rotation, revocation) MUST be audited:
- Who performed the operation
- When
- Which key
- Why

## 11. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
