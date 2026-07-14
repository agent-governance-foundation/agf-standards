# Specification 10: API Protocol

**Version:** 0.2.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.0  
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
