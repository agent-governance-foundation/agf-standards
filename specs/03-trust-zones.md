# Specification 03: Trust Zones (Local, Domain, Global)

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Profile  

## 1. Introduction

Trust in agent systems operates at multiple scopes. A single, global revocation state is operationally impossible. This specification defines three nested trust zones, each with its own authority, latency characteristics, and trust assumptions.

## 2. The Three Zones

### 2.1 Zone 1: Local Authority

**Scope:** Single agent boundary

**Location:** Within the agent's own execution context

**Authority:** The agent itself (cached delegations, local policies)

**Latency:** None (local computation)

**Trust Level:** Lowest (agent may be compromised)

**Delegation Depth Tracking:** Full chain (cached), max depth 10

**Use Cases:**
- Routine, low-risk actions (read public data)
- Offline operations (air-gapped environments)
- Performance-critical paths where network round-trip is impossible

**Components:**
- Local delegation cache
- Local policy cache
- Session-scoped credentials
- Capability declarations

**Cache Freshness:** Local cache MUST have a TTL (default: 5 minutes). After TTL, agent MUST re-validate with domain authority.

### 2.2 Zone 2: Domain Authority

**Scope:** Organization-wide trust

**Location:** Within the enterprise's controlled infrastructure

**Authority:** Enterprise trust service (the PDP and related services)

**Latency:** Network round-trip (typically 10–100ms)

**Trust Level:** High (enterprise-controlled, audited)

**Delegation Depth Tracking:** Full chain (source of truth), max depth 10

**Use Cases:**
- Most enterprise workflows
- Actions with moderate risk
- Delegation chains within the organization

**Components:**
- Agent identity registry
- Role-based policy inheritance
- Delegation chain validation
- Revocation list distribution
- Audit log aggregation

**Dominance:** The domain authority is the **primary** decision point for most enterprise deployments.

### 2.3 Zone 3: Global Authority

**Scope:** Cross-organization federation

**Location:** Public infrastructure or consortium-operated

**Authority:** Global trust registry (root of trust)

**Latency:** Variable (hundreds of milliseconds to seconds)

**Trust Level:** Medium (cryptographically verified, but no operational control)

**Delegation Depth Tracking:** First and last hop only (compressed), max depth 3

**Use Cases:**
- Cross-organization agent interactions
- Public verifiability requirements
- Root trust bootstrapping

**Components:**
- Federated agent identity (DID-based)
- Cross-org policy negotiation
- Verifiable audit attestations
- Open conformance standards

**Usage Pattern:** Global authority is invoked **rarely** (e.g., for initial identity verification, cross-org disputes). Domain authorities cache global trust assertions.

## 3. Zone Interaction

### 3.1 Policy Composition

Policies compose upward:

- **Local zone** can inherit and extend domain zone rules
- **Domain zone** can incorporate global zone attestations
- **Global zone** provides root trust but does not override domain policies

### 3.2 Decision Flow

```
Agent Action Request
│
▼
┌───────────────────┐
│    Local Zone     │
│  (cache + local   │─── Cache HIT ───▶ Decision
│    policies)      │
└─────────┬─────────┘
          │ Cache MISS
          ▼
┌───────────────────┐
│   Domain Zone     │
│ (enterprise PDP)  │─── Normal ──────▶ Decision
└─────────┬─────────┘
          │ Cross-org request
          ▼
┌───────────────────┐
│   Global Zone     │
│   (federation)    │─── Rare ────────▶ Decision
└───────────────────┘
```

### 3.3 Trust Decay Across Zones

| Direction | Trust Change | Rationale |
|-----------|--------------|-----------|
| Local → Domain | Trust increases | Domain authority is controlled |
| Domain → Global | Trust decreases (usually) | Global authority has less context |
| Global → Domain | Trust increases after verification | Domain validates global claims |

## 4. Zone-Specific Requirements

### 4.1 Local Zone Requirements

| Requirement | Description |
|-------------|-------------|
| Cache TTL | Maximum 5 minutes for delegation cache |
| Local Policy | Agent must have local policy for offline decisions |
| Audit | Local decisions MUST be logged and synced when online |
| Constraints | Local zone cannot override domain deny decisions |

**Offline behavior at cache expiry:**

When the local delegation cache expires (TTL exceeded) and the domain authority is unreachable:

| Scenario | Behavior |
|----------|----------|
| Inherent risk < 40 | `ALLOW_WITH_CAUTION` with `offline_fallback: true` in audit |
| Inherent risk 40–69 | `DENY` (fail closed) |
| Inherent risk ≥ 70 | `DENY` (fail closed) |
| Any cached delegation is expired | `DENY` (no extension regardless of risk) |

**Progressive risk penalty:**

For each hour beyond cache expiry, add +10 to inherent risk for offline decisions. After 4 hours without domain connectivity, all actions default to `DENY`.

**Example:**

```
Cache expires at T+5 min.
Action with inherent risk 35 at T+6 min  → ALLOW_WITH_CAUTION  (35 < 40)
Action with inherent risk 35 at T+65 min → inherent_risk + 10 = 45 → DENY
```

### 4.2 Domain Zone Requirements

| Requirement | Description |
|-------------|-------------|
| Availability | 99.9% uptime minimum |
| Latency | P99 < 100ms |
| Revocation Propagation | Within 60 seconds across domain |
| Audit Retention | Minimum 7 years (regulatory) |
| **Delegation Depth Tracked** | Full chain, up to depth 10 |

### 4.3 Global Zone Requirements

| Requirement | Description |
|-------------|-------------|
| Availability | 99.99% uptime (read-only) |
| Freshness | Global registry updated within 24 hours |
| Verification | All entries cryptographically verifiable |
| Dispute Resolution | Defined process for conflicting claims |
| **Delegation Depth Tracked** | First and last hop only, max depth 3 |

## 5. Example: Multi-Zone Delegation

### Scenario

Agent A (org1) needs to access a resource owned by Agent B (org2).

**Flow:**

1. **Local Zone (Agent A):** Checks local cache. No delegation found. Promotes to domain.
2. **Domain Zone (org1):** Validates org1's internal delegation chain. Determines cross-org access is needed.
3. **Global Zone:** Resolves Agent B's DID, retrieves org2's trust anchor.
4. **Domain Zone (org2):** Enforces org2's policies on the incoming request.
5. **Decision:** Returned to Agent A.

## 6. Global Zone Protocol

> **This section is superseded by Spec 27 (Global Trust Registry Protocol, `AGF-GTR-1.0`)**, which rewrites and extends the design below as its own numbered spec, cross-referenced against Specs 24-26's Trust Summary protocol. §6 is kept here for historical continuity rather than deleted; Spec 27 is the current source for this design.

### 6.1 Global Trust Registry

The global zone operates as a read-only registry of domain trust anchors.

**Endpoint (illustrative):** `https://global-registry.example.com/v1/trust-anchors`

> **Note:** The actual global registry URL will be published by the Agent Governance Foundation at [agentgovernancefoundation.com](https://agentgovernancefoundation.com) when the service is operational.

**Response:**

```json
{
  "anchors": [
    {
      "domain": "acme.com",
      "anchor_did": "did:agf:acme:service:trust-anchor",
      "verification_method": {...},
      "valid_from": 1735603200,
      "valid_until": 1767139200,
      "status": "active"
    }
  ],
  "signature": "base64...",
  "timestamp": 1735603200
}
```

### 6.2 Cross-Domain Delegation Flow

When Agent A (domain `acme.com`) needs to delegate to Agent B (domain `example.org`):

1. Acme PDP validates the internal chain (A's domain)
2. Acme PDP queries the global registry for `example.org`'s trust anchor
3. Acme PDP issues a cross-domain delegation token, signed by `acme.com`'s domain key
4. Example PDP receives the token and verifies:
   - Signature against `acme.com`'s trust anchor (from global registry)
   - Trust anchor validity (not expired, not revoked)
5. Example PDP applies its own policies to the cross-domain request

### 6.3 Trust Anchor Distribution

Global registry updates are published to:

- Well-known URL: `https://global-registry.example.com/.well-known/trust-anchors.json`
- CDN for low-latency global access
- Signed with the global root key

Domain authorities SHOULD cache trust anchors with TTL (default: 1 hour).

### 6.4 Dispute Resolution

If two domains disagree about a delegation's validity:

1. Each domain submits its evidence to the foundation's dispute registry
2. Foundation reviews:
   - Delegation chain signatures
   - Revocation state at time of decision
   - Policy versions in effect
3. Foundation issues a final ruling (binding for certified implementations)
4. Ruling published to global registry as a dispute record

**Dispute record format:**

```json
{
  "dispute_id": "dsp_1735603300_a1b2",
  "delegation_id": "del_abc123",
  "ruling": "VALID",
  "reasoning": "Chain signatures valid; revocation list was stale at time of decision",
  "issued_by": "did:agf:foundation:arbitration",
  "timestamp": 1735603300
}
```

## 7. Propagation Latency Requirements

| Propagation Path | Max Target | P99 Target | Action if Exceeded |
|------------------|------------|------------|-------------------|
| Global → Domain | 1 second | 500 ms | Retry, escalate to on-call |
| Domain → Local Cache | 5 seconds | 2 seconds | Fall back to direct verification |
| Local Cache invalidation | 500 ms | 200 ms | Agent re-verifies before next action |

## 8. Security Considerations

### 8.1 Zone Compromise

- **Local compromise** affects only that agent
- **Domain compromise** affects entire organization
- **Global compromise** affects cross-org trust (mitigated by multiple verification)

### 8.2 Zone Boundaries

Clear separation between zones prevents privilege escalation. Domain authorities MUST NOT trust local zone attestations without verification.

### 8.3 Propagation Delays

The system tolerates bounded propagation delays but MUST log and alert when delays exceed targets (see Section 7).

## 9. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
