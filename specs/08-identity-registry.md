# Specification 08: Identity Registry and DID Resolution

**Version:** 0.2.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.0  
**Layer:** Core format  

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

### 3.4 Identity Ownership and Key Binding

1. **Ownership.** Every registered identity is owned by exactly one organisation, or is the PDP's platform identity. Ownership is the registry's record. It MUST NOT be inferred from a DID's text, including its namespace (Spec 01 §2.6).
   - A DID names at most one registered identity across all identity kinds: agents, organisation identities and the platform identity. Registration MUST refuse a DID that already names a registered identity of any kind, atomically with the registration, so that of concurrent registrations of one DID at most one succeeds.
   - Two forms are reserved: the organisation-identity form (`did:agf:<namespace>:org:root`), which only an organisation identity may hold, and the PDP's platform DID, which no other identity may hold.
   - A lookup that finds more than one record for a DID, or a reserved form held by the wrong kind of identity, is a lookup **failure** (item 4), never a choice between the records.
2. **Keys.** An identity's keys are its registered verification methods. Where rotation applies, the key is the one covering the token's issue time (§4.2). A key belongs to an identity only if it is one of these.
3. **Resolution for verification.**
   - A key identifier selects candidate keys. Whether the key that verified a token belongs to the token's issuer is decided against the issuer identity's keys (Spec 02 §3.4).
   - A resolver that maps key identifiers to keys across all identities MAY supply candidates. It MUST NOT be taken as establishing that a key belongs to any particular identity.
   - A key identifier is not unique to one identity. A resolver MUST keep every identity's keys as candidates under a shared identifier; adding, replacing or removing one identity's key MUST NOT remove or replace another identity's. For an identity whose keys rotate (Spec 07 §4.5), its candidates are those its rotation rules allow at the token's issue time, and no copy of its keys held elsewhere may bypass those rules.
4. **Lookup outcomes.** A lookup returns the identity (with its owner, status and keys), or "not found", or fails.
   - A failure is never treated as either answer.
   - On decision, revalidation, recording and signing paths, "not found" and failure both deny (Spec 02 §3.10), in every environment.

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

A DID's text proves nothing about who controls it or which organisation owns it (§3.4). Implementations MUST NOT grant trust because an identifier resembles another organisation's, for example by embedding its namespace.

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
| 0.2.0 | 2026-10-08 | Draft: added §3.4 Identity Ownership and Key Binding: ownership is the registry's record, never inferred from a DID's text; an identity's keys are its registered verification methods; a deployment-wide key-identifier map supplies candidates only; a lookup returns the identity, not found, or a failure, and not found and failure both deny on decision, revalidation, recording and signing paths in every environment. §7.1 no trust from an identifier that resembles another organisation's. Identity names and key candidates (2026-10-14, draft): §3.4 item 1, a DID names at most one identity across kinds, with atomic registration and reserved organisation-identity and platform forms; an ambiguous lookup is a failure. §3.4 item 3, candidates under a shared key identifier are kept per identity |
