# Specification 08: Identity Registry and DID Resolution

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.0

## 1. Introduction

Agents need verifiable identities. This specification defines the identity registry, DID document format, key binding, and resolution interface.

## 2. Agent Identity

### 2.1 DID Format

```
did:agf:{namespace}:{specific-id}
```

**Examples:**
- `did:agf:acme:agent:build-server-01`
- `did:agf:example:alice`

### 2.2 DID Document

```json
{
  "@context": "https://www.w3.org/ns/did/v1",
  "id": "did:agf:acme:agent:build-server-01",
  "controller": "did:agf:acme:service:it",
  "verification_method": [
    {
      "id": "did:agf:acme:agent:build-server-01#key-1",
      "type": "JsonWebKey2020",
      "controller": "did:agf:acme:agent:build-server-01",
      "publicKeyJwk": {
        "kty": "EC",
        "crv": "P-256",
        "x": "...",
        "y": "..."
      }
    }
  ],
  "authentication": ["#key-1"],
  "assertion_method": ["#key-1"],
  "capability_delegation": ["#key-1"],
  "service": [
    {
      "id": "#pdp",
      "type": "PolicyDecisionPoint",
      "serviceEndpoint": "https://pdp.acme.com"
    }
  ],
  "created": "2026-06-10T00:00:00Z",
  "updated": "2026-06-10T00:00:00Z"
}
```

A conformant implementation SHOULD add a `status` field (e.g. `"status": "active"`) to the DID document, alongside `created`/`updated`, to represent identity lifecycle state without requiring a separate revocation lookup.

## 3. Identity Registry

### 3.1 Purpose

The identity registry:
- Issues agent DIDs
- Stores DID documents
- Manages key rotation
- Provides resolution endpoint

### 3.2 Registry API

*(The request/response shapes below are illustrative of the protocol's data model.)*

**`POST /v1/identities`** — Create a new agent identity

Request:

```json
{
  "controller": "did:agf:acme:service:it",
  "verification_method": {...},
  "services": [...]
}
```

Response:

```json
{
  "did": "did:agf:acme:agent:new-01",
  "document": {...},
  "created_at": 1735603200
}
```

**`GET /v1/identities/{did}`** — Resolve DID to document

**`PUT /v1/identities/{did}`** — Update DID document (key rotation, service updates)

**`POST /v1/identities/{did}/revoke`** — Revoke an agent identity (emergency only)

### 3.3 Resolution

Resolution MUST support:
- Direct lookup from registry
- Cached resolution with bounded staleness: either a TTL (default: 300 seconds) or push-based invalidation that converges faster than any reasonable TTL (e.g. broadcasting key changes to every node in the same transaction as the key change, so caches converge within tens of milliseconds)
- DID method specification

A key resolver MAY combine multiple key sources (e.g. filesystem keys and a database-backed cache of agent keys) — see Spec 09 for where key storage belongs normatively.

## 4. Key Management

### 4.1 Key Types

| Key Type | Algorithm | Use |
|----------|-----------|-----|
| Signing | ES256 | Sign delegations |
| Verification | ES256 | Verify signatures |
| Encryption | ECDH-ES | Secure communication |

### 4.2 Key Rotation

Keys SHOULD be rotated:
- Every 90 days for agents
- Every 365 days for root authorities

**Rotation process:**
1. Generate new key pair
2. Add new verification method to DID document
3. Wait for propagation (TTL × 2)
4. Begin signing with new key
5. Remove old verification method

### 4.3 Key Revocation

If a key is compromised:
1. Remove verification method from DID document
2. Add key to revocation list
3. Rotate all delegations signed with that key

## 5. Trust Anchors

### 5.1 Root Trust

The global zone maintains a list of trusted domain anchors:

```json
{
  "domain": "acme.com",
  "anchor_did": "did:agf:acme:service:trust-anchor",
  "verification_method": {...},
  "valid_from": 1735603200,
  "valid_until": 1767139200
}
```

### 5.2 Trust Verification

When verifying a cross-domain delegation:
1. Resolve the domain's trust anchor
2. Verify the domain's signature on the delegation
3. Check that the domain anchor is trusted

## 6. Example: Agent Lifecycle

### 6.1 Registration

```
Admin → POST /v1/identities
              ↓
      Registry creates DID and key
              ↓
      Registry returns DID document
```

### 6.2 Delegation

```
Agent A (did:agf:acme:agent:a)
    → signs delegation
    → includes key ID from DID document
```

### 6.3 Verification

```
Verifier → GET /v1/identities/did:agf:acme:agent:a
                 ↓
         Registry returns DID document
                 ↓
         Verifier extracts public key
                 ↓
         Verifies delegation signature
```

### 6.4 Key Rotation

```
Agent A → PUT /v1/identities/did:agf:acme:agent:a
                (with new verification_method)
                ↓
        Registry updates document
                ↓
        Wait TTL
                ↓
        Agent A signs new delegations with new key
```

## 7. Security Considerations

### 7.1 DID Squatting

Prevent impersonation by requiring proof of control:
- New DIDs must be signed by controller's existing key
- First DID for a controller requires out-of-band verification

### 7.2 Resolution Latency

Caching reduces latency but introduces propagation delay. Critical verifications SHOULD resolve directly.

### 7.3 Registry Compromise

If registry is compromised:
- All DIDs issued by registry become untrusted
- Use global zone trust anchors as fallback
- Emergency revocation: publish compromised registry to global revocation list

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
