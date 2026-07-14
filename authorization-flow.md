# Agent Governance Foundation — Complete Authorization Flow

**Document Version:** 1.0.0  
**Date:** 2026-07-12  
**Status:** Living Document

## Table of Contents

1. [Overview](#1-overview)
2. [Core Concepts](#2-core-concepts)
3. [Phase 1: Bootstrap (Setup)](#3-phase-1-bootstrap-setup)
4. [Phase 2: Identity Registration](#4-phase-2-identity-registration)
5. [Phase 3: Delegation Issuance](#5-phase-3-delegation-issuance)
6. [Phase 4: Authorization Request](#6-phase-4-authorization-request)
7. [Phase 5: Trust Evaluation](#7-phase-5-trust-evaluation)
8. [Phase 6: Risk Evaluation](#8-phase-6-risk-evaluation)
9. [Phase 7: Policy Evaluation](#9-phase-7-policy-evaluation)
10. [Phase 8: Final Decision](#10-phase-8-final-decision)
11. [Phase 9: Audit](#11-phase-9-audit)
12. [Phase 10: Revocation](#12-phase-10-revocation)
13. [Complete Sequence Diagram](#13-complete-sequence-diagram)
14. [Example End-to-End Walkthrough](#14-example-end-to-end-walkthrough)
15. [Error Handling](#15-error-handling)
16. [Glossary](#16-glossary)

## 1. Overview

This document describes the complete end-to-end flow of the Agent Governance Foundation (AGF) authorization system. It shows how an autonomous agent receives authority through delegation chains, requests an action, and is evaluated for trust, risk, and policy compliance — all while producing auditable, verifiable artifacts.

The core question the system answers:

> "Can Agent X perform Action Y on Resource Z right now?"

The answer includes:

- Allow/Deny decision
- Trust score (0–100)
- Risk score (0–100)
- Audit artifact (signed, replayable)

The flow below exercises all six AAP-Core kernel objects ([Spec 00](specs/00-aap-core.md)): the **Actor** registers an identity (Phase 2), receives **Authority** through delegation (Phase 3), attempts an **Action** (Phase 4), gets a **Decision** with a policy version (Phases 5–8), leaves a signed **Receipt** trail (Phase 9), and can lose authority through **Invalidation** (Phase 10). If you want the minimal normative model before the full walkthrough, read Spec 00 first.

## 2. Core Concepts

| Concept | Definition | Where Defined |
|---------|------------|---------------|
| Delegation Token | Signed JWT granting authority from issuer to subject | Spec 01 |
| Delegation Chain | Ordered list of tokens from root to leaf agent | Spec 02 |
| Trust Zone | Local, Domain, or Global scope of authority | Spec 03 |
| Trust Score | 0–100 score based on chain depth, age, revocation | Spec 04 |
| Risk Score | Combination of inherent, environmental, and trust risk | Spec 04 |
| Policy | Business rules written in Rego (OPA) | Spec 06 |
| Decision Artifact | Signed, self-contained proof of every decision | Spec 07 |
| Revocation List | Signed list of revoked delegation IDs (branch cut) | Spec 05 |

## 3. Phase 1: Bootstrap (Setup)

Before any agent can act, the foundational infrastructure must be established.

### 3.1 Generate Root Keys

```bash
# Generate root signing key (HSM recommended)
openssl ecparam -name prime256v1 -genkey -noout -out root-private.pem
openssl ec -in root-private.pem -pubout -out root-public.pem
```

### 3.2 Establish Global Trust Registry

> **Note:** `global-registry.example.com` is an illustrative placeholder. The actual global registry URL will be published by the Agent Governance Foundation at [agentgovernancefoundation.com](https://agentgovernancefoundation.com) when the service is operational.

The foundation operates a global trust registry at `https://global-registry.example.com/v1/trust-anchors`.

Initial entry:

```json
{
  "domain": "acme.com",
  "anchor_did": "did:agf:acme:service:trust-anchor",
  "verification_method": {},
  "valid_from": 1735603200,
  "valid_until": 1767139200,
  "signature": "..."
}
```

### 3.3 Deploy Domain Services

> **Implementation note:** the table below is the protocol's vendor-neutral illustrative topology — six independently deployable services. A conformant implementation MAY collapse trust evaluation, risk evaluation, and final-decision combining into a single in-process service instead of separate service boundaries at HTTP level — this document describes the protocol-level shape, not a required deployment topology.

Each domain (enterprise) deploys, per the protocol's illustrative topology:

| Service | Purpose | Port |
|---------|---------|------|
| Identity Registry | DID registration/resolution | 8000 |
| Trust Evaluator | Chain validation + trust score | 8001 |
| Risk Evaluator | Inherent + environmental risk | 8002 |
| Policy Engine | OPA policy evaluation | 8003 |
| PDP | Final decision combining | 8004 |
| Audit Service | Signed artifact storage | 8005 |

## 4. Phase 2: Identity Registration

Before receiving delegations, agents must have verifiable identities.

### 4.1 Register Human Root Authority

Alice (human) registers as a root authority:

```bash
POST /v1/identities
{
  "controller": "did:agf:acme:service:it",
  "verification_method": {
    "type": "JsonWebKey2020",
    "publicKeyJwk": {}
  }
}
```

Response:

```json
{
  "did": "did:agf:acme:alice",
  "document": {},
  "created_at": 1735603200
}
```

### 4.2 Register Agent

Agent Builder (an autonomous agent) registers:

```bash
POST /v1/identities
{
  "controller": "did:agf:acme:alice",
  "verification_method": {}
}
```

Response:

```json
{
  "did": "did:agf:acme:agent:builder",
  "document": {}
}
```

### 4.3 DID Resolution

When any verifier needs to validate a signature:

```bash
GET /v1/identities/did:agf:acme:agent:builder
```

Response: DID document containing the agent's public key.

Caching: Resolved DIDs are cached for 300 seconds.

## 5. Phase 3: Delegation Issuance

Authority flows from humans to agents via signed delegation tokens.

### 5.1 Root Delegation (Alice → Agent Builder)

Alice issues a delegation to Agent Builder:

```python
payload = {
    "iss": "did:agf:acme:alice",
    "sub": "did:agf:acme:agent:builder",
    "aud": "https://pdp.acme.com",
    "exp": 1735689600,
    "iat": 1735603200,
    "jti": "del_7f3e9a2b",
    "scope": ["read:source-code", "run:build", "execute:deployment", "delegate:run"],
    "max_depth": 3
}
token = jwt.encode(payload, alice_private_key, algorithm="ES256")
```

Agent Builder receives and stores this token.

### 5.2 Sub-Delegation (Agent Builder → Agent Deployer)

Agent Builder delegates to Agent Deployer:

```python
payload = {
    "iss": "did:agf:acme:agent:builder",
    "sub": "did:agf:acme:agent:deployer",
    "aud": "https://pdp.acme.com",
    "exp": 1735675200,
    "iat": 1735603200,
    "jti": "del_9c2d8f1e",
    "parent": "del_7f3e9a2b",
    "scope": ["run:build", "execute:deployment"],
    "max_depth": 2,
    "constraints": {
        "time_of_day": ["09:00-17:00"]
    }
}
token = jwt.encode(payload, builder_private_key, algorithm="ES256")
```

### 5.3 Chain Formation

The delegation chain is now:

- Token 1: Alice → Builder (scope: `read:source-code`, `run:build`, `execute:deployment`, `delegate:run`)
- Token 2: Builder → Deployer (scope: `run:build`, `execute:deployment`)

```
Effective scope = Intersection = [run:build, execute:deployment]
```

Scope is strictly narrowing: Deployer cannot acquire any scope that Builder did not already hold (see Spec 02 §3.5).

## 6. Phase 4: Authorization Request

Agent Deployer needs to execute a deployment.

### 6.1 Request Format

```json
POST /v1/decide
{
  "chain": [
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9...",
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9..."
  ],
  "action": {
    "type": "execute:deployment",
    "resource": "production/web-app"
  },
  "context": {
    "timestamp": 1735603300,
    "source_ip": "10.0.1.45",
    "location": "office"
  }
}
```

### 6.2 Local Zone Check (Cache)

Agent Deployer first checks its local cache (TTL: 5 minutes):

- If a cached decision exists and is not expired → return cached decision
- If cache miss or expired → proceed to domain PDP

## 7. Phase 5: Trust Evaluation

PDP calls Trust Evaluator (`POST /v1/evaluate`).

### 7.1 Input to Trust Evaluator

```json
{
  "chain": ["jwt_1", "jwt_2"],
  "action": {"type": "execute:deployment"},
  "context": {"timestamp": 1735603300},
  "revocation_list_url": "https://acme.com/revocations.json"
}
```

### 7.2 Validation Steps (Per Token)

| Step | Check | Failure Code |
|------|-------|-------------|
| 1 | Signature valid | `INVALID_SIGNATURE` |
| 2 | Expiration (`exp > now`) | `EXPIRED` |
| 3 | Revocation check | `REVOKED` |
| 4 | Continuity (`sub == next.iss`) | `CHAIN_BROKEN` |
| 5 | Depth limit (`max_depth`) | `DEPTH_EXCEEDED` |
| 6 | Constraints (time, location) | `CONSTRAINT_VIOLATION` |
| 7 | Scope intersection | `SCOPE_INSUFFICIENT` |

### 7.3 Trust Score Calculation

- Base score: 100
- Depth: 2 hops → −5 (1 extra level × −5)
- Age: 4 hours → −8 (4 × −2)
- Stale revocation list: 0
- Unknown issuer: 0

**Trust Score: 100 − 5 − 8 = 87**

### 7.4 Trust Evaluator Response

```json
{
  "trust_score": 87,
  "decision": "ALLOW",
  "penalties": {
    "depth": {"hops": 2, "penalty": -5},
    "age_hours": {"value": 4, "penalty": -8}
  },
  "lineage_depth": 2,
  "revoked": false,
  "expired": false
}
```

## 8. Phase 6: Risk Evaluation

PDP calls Risk Evaluator (`POST /v1/risk`).

### 8.1 Input to Risk Evaluator

```json
{
  "action": {"type": "execute:deployment", "resource": "production/web-app"},
  "context": {
    "timestamp": 1735603300,
    "source_ip": "10.0.1.45",
    "location": "office"
  },
  "trust_score": 87
}
```

### 8.2 Inherent Risk Lookup

From policy repository:

```json
{
  "action_type": "execute:deployment",
  "conditions": [
    {"resource_pattern": "production/*", "risk": 70},
    {"resource_pattern": "staging/*", "risk": 40}
  ],
  "default_risk": 50
}
```

Resource `production/web-app` matches → **Inherent risk = 70**

### 8.3 Environmental Risk Evaluation

| Factor | Value | Modifier |
|--------|-------|---------|
| Time | 10:00 AM (office hours) | +0 |
| Location | office | +0 |
| Velocity | first request in 10 seconds | +0 |
| IP | trusted range | +0 |

**Environmental risk = 0**

### 8.4 Trust Weight

Linear weighting (default): `trust_weight = 87 / 100 = 0.87`

### 8.5 Final Risk Calculation

```
final_risk = inherent + (environmental × trust_weight)
final_risk = 70 + (0 × 0.87) = 70
```

### 8.6 Decision Mapping

| Final Risk | Decision |
|------------|----------|
| 0–39 | `ALLOW` |
| 40–69 | `ALLOW_WITH_CAUTION` |
| 70–100 | `REVIEW_REQUIRED` |
| > 100 | `DENY` (capped at 100) |

Final Risk = 70 → **REVIEW_REQUIRED**

### 8.7 Risk Evaluator Response

```json
{
  "inherent_risk": 70,
  "environmental_risk": 0,
  "trust_weight": 0.87,
  "final_risk": 70,
  "decision": "REVIEW_REQUIRED"
}
```

## 9. Phase 7: Policy Evaluation

PDP calls Policy Engine (`POST /v1/evaluate`).

### 9.1 Input to Policy Engine

```json
{
  "policy_version": "acme/policies/deployment/production@1.2.0",
  "input": {
    "action": {"type": "execute:deployment", "resource": "production/web-app"},
    "subject": "did:agf:acme:agent:deployer",
    "trust_score": 87,
    "risk_score": 70,
    "chain_valid": true,
    "depth": 2,
    "context": {"time_of_day": "10:00", "location": "office"}
  }
}
```

### 9.2 Policy Evaluation (OPA/Rego)

```rego
allow {
    input.action.type = "execute:deployment"
    input.risk_score < 80
    input.chain_valid
    has_approval(input.context)
}

allow_with_caution {
    input.action.type = "execute:deployment"
    input.risk_score >= 80
    input.risk_score < 95
    input.chain_valid
    has_peer_approval(input.context)
}

deny {
    input.action.type = "execute:deployment"
    input.risk_score >= 95
}
```

`risk_score = 70 < 80` → `allow` rule matches.

### 9.3 Policy Engine Response

```json
{
  "allow": true,
  "allow_with_caution": false,
  "deny": false,
  "reason": ["input.risk_score < 80", "input.chain_valid"],
  "policy_hash": "sha256:abc123..."
}
```

## 10. Phase 8: Final Decision

PDP combines trust, risk, and policy results. **Elevated risk is never overridden by an explicit policy allow** — an agent that passes policy but trips risk thresholds still gets routed to human review. This is deny-overrides-allow with risk given precedence over policy on the allow side, not "policy has final say."

### 10.1 Decision Logic

```python
def make_decision(trust_result, risk_decision, policy_decision):
    # 1. Hard failures from trust evaluation short-circuit before merge is ever
    #    reached — these never go through the precedence chain below.
    if trust_result.get("revoked") or trust_result.get("expired"):
        return "DENY", "Trust chain invalid"

    # 2. merge_decisions(risk_decision, policy_decision): deny-overrides-allow,
    #    and risk's REVIEW_REQUIRED beats an explicit policy ALLOW.
    if policy_decision == "DENY":
        return "DENY", "Policy denied"

    if risk_decision == "DENY":
        return "DENY", "Risk score exceeded deny threshold"

    if risk_decision == "REVIEW_REQUIRED":
        return "REVIEW_REQUIRED", "Elevated risk requires human review, regardless of policy allow"

    if policy_decision == "ALLOW_WITH_CAUTION":
        return "ALLOW_WITH_CAUTION", "Policy allowed with caution"

    if risk_decision == "ALLOW_WITH_CAUTION":
        return "ALLOW_WITH_CAUTION", "Risk allowed with caution"

    if policy_decision == "ALLOW":
        return "ALLOW", "Policy allowed"

    if risk_decision == "ALLOW":
        return "ALLOW", "Risk allowed"

    # 3. Nothing matched — default to REVIEW_REQUIRED, not DENY.
    return "REVIEW_REQUIRED", "No applicable allow rule; defaulting to human review"
```

> **Precedence, in order:** trust revoked/expired → policy DENY → risk DENY → risk REVIEW_REQUIRED → policy ALLOW_WITH_CAUTION → risk ALLOW_WITH_CAUTION → policy ALLOW → risk ALLOW → default REVIEW_REQUIRED.

### 10.2 PDP Response

Trust (87) and policy (`allow=true`) both cleared, but risk resolved to `REVIEW_REQUIRED` (§8.6) — per the precedence above, that wins over the policy allow:

```json
{
  "data": {
    "decision": "REVIEW_REQUIRED",
    "trust_score": 87,
    "risk_score": 70,
    "policy_version": "acme/policies/deployment/production@1.2.0",
    "artifact_id": "dec_1735603300_a1b2c3"
  },
  "meta": {
    "request_id": "req_1735603300_xyz",
    "timestamp": 1735603301
  }
}
```

## 11. Phase 9: Audit

Every decision creates a signed, immutable artifact.

### 11.1 Decision Artifact

```json
{
  "artifact_id": "dec_1735603300_a1b2c3",
  "schema_version": "1.0",
  "timestamp": 1735603300,
  "verifier_id": "https://pdp.acme.com",
  "request": {
    "delegation_chain": ["jwt_1", "jwt_2"],
    "action": {"type": "execute:deployment", "resource": "production/web-app"},
    "context": {"timestamp": 1735603300, "source_ip": "10.0.1.45"}
  },
  "response": {
    "decision": "REVIEW_REQUIRED",
    "trust_score": 87,
    "risk_score": 70,
    "reasoning": [
      "input.risk_score < 80", 
      "input.chain_valid", 
      "risk.decision=REVIEW_REQUIRED overrides policy.allow"],
    "penalties": {
      "depth": {"hops": 2, "penalty": -5},
      "age_hours": {"value": 4, "penalty": -8}
    }
  },
  "policy": {
    "version": "acme/policies/deployment/production@1.2.0",
    "policy_hash": "sha256:abc123..."
  },
  "revocation_state": {
    "list_version": "1",
    "list_hash": "sha256:def456...",
    "list_valid_until": 1735689600
  },
  "signatures": [
    {
      "signer": "did:agf:acme:pdp-01",
      "algorithm": "ES256",
      "signature": "base64...",
      "timestamp": 1735603301
    }
  ]
}
```

### 11.2 Storage

Artifact stored at:

```
audit-logs/2026/06/10/dec_1735603300_a1b2c3.json
```

### 11.3 Verification (Future Audit)

Auditor retrieves and verifies:

```bash
GET /v1/artifacts/dec_1735603300_a1b2c3
```

Verification steps:

1. Verify PDP signature against domain trust anchor
2. Confirm policy version existed at decision time
3. Review revocation state
4. Accept or reject decision

## 12. Phase 10: Revocation

Authority can be revoked before expiration.

### 12.1 Revoke Delegation

```bash
POST /v1/revocations
{
  "delegation_id": "del_9c2d8f1e",
  "reason": "mission_complete",
  "revoked_by": "did:agf:acme:alice"
}
```

### 12.2 Branch Cut Effect

Revoking `del_9c2d8f1e` (Builder → Deployer) cuts the branch:

- Agent Deployer loses all authority
- Any child delegations from Deployer also become invalid
- Agent Builder retains authority (different branch)

### 12.3 Revocation List Update

```json
{
  "version": "2",
  "issued_at": 1735689600,
  "valid_until": 1735693200,
  "revocations": [
    {"delegation_id": "del_9c2d8f1e", "revoked_at": 1735689600, "reason": "mission_complete"}
  ]
}
```

### 12.4 Future Request with Revoked Chain

When Deployer attempts another action, trust evaluation detects the revocation and returns `DENY`.

## 13. Complete Sequence Diagram

```
Agent Deployer          PDP              Trust Eval        Risk Eval         Policy Eng        Audit Svc
     │                   │                   │                 │                 │                │
     │ POST /v1/decide   │                   │                 │                 │                │
     │──────────────────▶│                   │                 │                 │                │
     │                   │                   │                 │                 │                │
     │                   │ POST /v1/evaluate │                 │                 │                │
     │                   │──────────────────▶│                 │                 │                │
     │                   │                   │                 │                 │                │
     │                   │   trust_score=87  │                 │                 │                │
     │                   │◀──────────────────│                 │                 │                │
     │                   │                   │                 │                 │                │
     │                   │ POST /v1/risk     │                 │                 │                │
     │                   │──────────────────────────────────▶│                 │                │
     │                   │                   │                 │                 │                │
     │                   │   risk_decision=REVIEW_REQUIRED    │                 │                │
     │                   │◀──────────────────────────────────│                 │                │
     │                   │                   │                 │                 │                │
     │                   │ POST /v1/evaluate │                 │                 │                │
     │                   │─────────────────────────────────────────────────────▶│                │
     │                   │                   │                 │                 │                │
     │                   │   allow=true      │                 │                 │                │
     │                   │◀─────────────────────────────────────────────────────│                │
     │                   │                   │                 │                 │                │
     │                   │ POST /v1/artifacts│                 │                 │                │
     │                   │─────────────────────────────────────────────────────────────────────▶│
     │                   │                   │                 │                 │                │
     │                   │   artifact_id     │                 │                 │                │
     │                   │◀─────────────────────────────────────────────────────────────────────│
     │                   │                   │                 │                 │                │
     │ decision=REVIEW_REQUIRED              │                 │                 │                │
     │◀──────────────────│                   │                 │                 │                │
     │                   │                   │                 │                 │                │
```

## 14. Example End-to-End Walkthrough

### Scenario

Agent Deployer wants to execute a production deployment at 10:00 AM.

### Preconditions

- Alice (human) has registered DID: `did:agf:acme:alice`
- Builder agent has DID: `did:agf:acme:agent:builder`
- Deployer agent has DID: `did:agf:acme:agent:deployer`
- Delegation chain: Alice → Builder → Deployer
- Policy: Production deployment requires risk < 80

### Flow

| Step | Component | Input | Output |
|------|-----------|-------|--------|
| 1 | Agent Deployer | User action | `POST /v1/decide` with chain |
| 2 | PDP (cache) | Check local cache | Cache miss |
| 3 | Trust Evaluator | Chain + action | `trust_score=87`, valid |
| 4 | Risk Evaluator | Action + trust_score | inherent=70, environmental=0, final=70 → `REVIEW_REQUIRED` |
| 5 | Policy Engine | risk_score=70 | `allow=true` (risk < 80) |
| 6 | PDP Decision | trust=87, risk_decision=REVIEW_REQUIRED, policy=allow | `REVIEW_REQUIRED` (risk's REVIEW_REQUIRED overrides policy's allow — see §10.1) |
| 7 | Audit Service | Full decision | Signed artifact stored |
| 8 | Agent Deployer | Response | Deployment held; routed to human approval (Spec 15) |

### Outcome

**REVIEW_REQUIRED** — Deployment is held pending human sign-off. The policy engine's `allow` reflects that risk was an acceptable *input* to policy (`< 80`); it does not mean risk is waived. Every step is still auditable, and the artifact records both the policy's reasoning and the risk override that produced the final decision.

## 15. Error Handling

| Error | Phase | HTTP Status | Recovery |
|-------|-------|-------------|----------|
| Invalid signature | Trust | 400 | Reject chain |
| Expired token | Trust | 400 | Reject chain |
| Revoked delegation | Trust | 400 | Reject chain |
| Constraint violation | Trust | 400 | Reject chain |
| Scope insufficient | Trust | 403 | Reject action |
| Revocation list stale (1–24h) | Trust | 200 (with penalty) | Cap to `ALLOW_WITH_CAUTION` |
| Revocation list stale (> 24h) | Trust | 500 | Reject; must refresh |
| Policy version not found | Policy | 404 | Fallback or reject |
| PDP unavailable | Decision | 503 | Retry with backoff; fallback to local cache |
| Audit service unavailable | Audit | 500 | Log locally; sync later |

## 16. Glossary

| Term | Definition |
|------|------------|
| Branch Cut | Revocation model where revoking a parent delegation invalidates all descendants |
| Delegation Chain | Ordered list of tokens from root authority to leaf agent |
| DID | Decentralized Identifier — verifiable agent identity |
| Environmental Risk | Risk from context (time, location, velocity) |
| Inherent Risk | Risk intrinsic to the action type (e.g., delete backup = high) |
| JWT | JSON Web Token — format for delegation tokens |
| PDP | Policy Decision Point — final decision orchestrator |
| Rego | Policy language (Open Policy Agent) |
| Revocation List | Signed list of revoked delegation IDs |
| Trust Score | 0–100 score based on chain depth, age, and revocation state |
| Trust Zone | Local, Domain, or Global authority scope |
