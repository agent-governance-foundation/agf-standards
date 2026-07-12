# Specification 20: Operational Reality

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None

## 1. Introduction

The core specifications (01-19) define what the system does. This specification defines **operational reality** — the constraints, budgets, and failure modes that determine whether the system works in production at scale.

This specification cross-references and extends multiple existing specifications. Where conflicts exist, this specification takes precedence for operational deployments.

## 2. Cross-Cutting Operational Constraints

### 2.1 Performance Budgets

| Operation | P99 Target | Maximum | Measurement Window |
|-----------|------------|---------|--------------------|
| Token verification (single) | 1 ms | 5 ms | 1 minute |
| Chain validation (depth=3) | 10 ms | 30 ms | 1 minute |
| Chain validation (depth=10) | 30 ms | 80 ms | 1 minute |
| Trust score calculation | 5 ms | 15 ms | 1 minute |
| Risk evaluation | 10 ms | 25 ms | 1 minute |
| Policy evaluation (OPA) | 15 ms | 40 ms | 1 minute |
| Full PDP decision (cached) | 25 ms | 60 ms | 1 minute |
| Full PDP decision (uncached) | 50 ms | 120 ms | 1 minute |

### 2.2 Scalability Targets

| Metric | Target | Degradation Point |
|--------|--------|-------------------|
| Decisions per second (single PDP) | 1,000 | 2,000 |
| Decisions per second (cluster) | 10,000 | 20,000 |
| Active delegation chains | 1,000,000 | 5,000,000 |
| Revocation list entries | 100,000 | 500,000 |
| Audit events per day | 10,000,000 | 50,000,000 |
| Concurrent agents per domain | 100,000 | 500,000 |

### 2.3 Availability Targets

| Component | Target Uptime | Allowed Downtime/Year | Failure Mode |
|-----------|---------------|----------------------|--------------|
| Identity Registry | 99.9% | 8.76 hours | Read-only fallback |
| Trust Evaluator | 99.95% | 4.38 hours | Local cache fallback |
| PDP (primary) | 99.99% | 52 minutes | Secondary region |
| Audit Service | 99.95% | 4.38 hours | Local buffer |
| Global Registry | 99.99% | 52 minutes | CDN cache |

### 2.4 Propagation Latency SLIs

| Propagation Path | Target (P99) | Alert at (P99) | Critical at (P99) |
|------------------|--------------|----------------|-------------------|
| Revocation issue → Global | 200 ms | 500 ms | 1 second |
| Global → Domain | 500 ms | 1 second | 2 seconds |
| Domain → Local cache | 2 seconds | 5 seconds | 10 seconds |
| Policy update → PDP | 30 seconds | 60 seconds | 120 seconds |

## 3. Delegation Depth (Extends Spec 02, Spec 03)

### 3.1 Depth Limits by Zone

| Zone | Max Tracked Depth | Hard Limit | Behavior When Exceeded |
|------|-------------------|------------|------------------------|
| Local (cache) | 10 | 20 | Cache miss, escalate to domain |
| Domain (source) | 10 | 20 | Reject with `MAX_DEPTH_EXCEEDED` |
| Global (compressed) | 3 | 5 | Compress to first+last hop |

*(Only the "Domain" row is real: hard limit 20 is enforced, soft limit 10 is defined but unenforced. Local and Global zones don't exist — see Spec 03.)*

### 3.2 Depth Performance Model

| Depth | Signature Verifications | Validation Time (est.) | Trust Penalty |
|-------|------------------------|------------------------|---------------|
| 1 | 1 | 2 ms | 0 |
| 2 | 2 | 4 ms | -5 |
| 3 | 3 | 6 ms | -10 |
| 5 | 5 | 10 ms | -20 |
| 10 | 10 | 20 ms | -45 |

### 3.3 Depth Exceeded Recovery

When chain depth exceeds hard limit:

1. Return `DENY` with error code `MAX_DEPTH_EXCEEDED`
2. Log the full chain (truncated to first 10 hops + last hop)
3. Alert security team if frequency > 10/hour
4. Consider recertification of the root issuer

## 4. Revocation Propagation (Extends Spec 05)

### 4.1 Propagation Window Behavior

During the propagation window (between revocation issuance and cache invalidation):

| Action Time | Behavior | Audit Annotation |
|-------------|----------|------------------|
| Within 0-500ms | `DENY` (safe) | `propagation_window: true` |
| Within 500ms-2s | `DENY` (safe) | `propagation_window: true, latency_warning: true` |
| Within 2s-5s | `DENY` (degraded) | `propagation_window: true, degraded: true` |
| > 5s | `DENY` + escalate | `propagation_window_exceeded: true` |

*(None of these four graduated-response tiers are implemented as distinct behaviors — propagation latency is backend-dependent, and the direct-query backend described in Spec 05 has no real "propagation window" to bound in the first place.)*

### 4.2 Stale List Graduated Response

*(Not yet implemented — see Spec 05. No trust penalty, decision cap, or audit flag exists for revocation staleness, since there is no "list" with a staleness concept in this implementation.)*

| Staleness | Trust Penalty | Decision Cap | Audit Flag |
|-----------|---------------|--------------|------------|
| 0-1 hour | -20 | None | `revocation_list: stale` |
| 1-24 hours | -20 | `ALLOW_WITH_CAUTION` | `revocation_list: stale_capped` |
| >24 hours | N/A | `DENY` | `revocation_list: expired` |

### 4.3 Cache Invalidation Strategy

```yaml
cache_invalidation:
  strategy: "WRITE_INVALIDATE"  # Invalidate on revocation write
  propagation:
    broadcast: true
    retry_count: 3
    retry_backoff_ms: 100
  fallback:
    on_no_acknowledgment: "FORCE_REVALIDATE"
    force_revalidate_actions: ["approve:payment", "delete:backup"]
```

## 5. Policy Conflict Resolution (Extends Spec 06)

### 5.1 Zone Precedence Table

| Zone | Allow Weight | Deny Weight | Override Rule |
|------|-------------|-------------|---------------|
| Global | 1 | 100 | Deny always wins |
| Domain | 2 | 50 | Deny overrides Local allow |
| Local | 3 | 10 | Allow only if no higher deny |

### 5.2 Conflict Resolution Algorithm

```python
def resolve_policy_conflict(results):
    # Sort by zone precedence (lower weight = higher precedence)
    sorted_results = sorted(results, key=lambda x: ZONE_PRECEDENCE[x.zone])

    # First deny wins
    for result in sorted_results:
        if result.decision == "DENY":
            return result

    # Then first allow
    for result in sorted_results:
        if result.decision == "ALLOW":
            return result

    # Default deny
    return Decision(decision="DENY", reason="No applicable allow rule")
```

### 5.3 Conflict Detection

Conflicts MUST be detected when:

- Same zone, same agent, same action → different outcomes (policy bug)
- Different zones, different outcomes → logged for audit

Alert when:

- Same-zone conflicts > 1/hour
- Different-zone conflicts > 10/hour (indicates policy drift)

## 6. Audit Storage Economics (Extends Spec 07)

### 6.1 Sampling Rates by Risk Tier

*(Not built — the real behavior is safer than this table, at higher storage cost. Every decision is currently retained regardless of risk tier, equivalent to this table's Tier 3/100% row; there is no cost-reduction sampling for low-risk actions, so the blended storage-cost model in §6.3 below doesn't apply to actual volume.)*

### 6.2 Compression Targets

| Data Type | Raw Size | Compressed (zstd) | Ratio |
|-----------|----------|-------------------|-------|
| Single decision artifact | 2 KB | 200 B | 10:1 |
| Aggregated summary | 200 B | 100 B | 2:1 |
| Batch of 1000 decisions | 2 MB | 150 KB | 13:1 |

### 6.3 Storage Cost Model (Example)

**Assumptions:**
- 10 million decisions/day
- 70% Tier 1, 20% Tier 2, 10% Tier 3
- zstd compression (10:1)
- S3 storage pricing

| Tier | Raw GB/day | Compressed GB/day | Monthly Cost |
|------|------------|-------------------|--------------|
| Tier 1 (1% sample) | 14 | 1.4 | $4 |
| Tier 2 (10% sample) | 40 | 4 | $12 |
| Tier 3 (100%) | 200 | 20 | $60 |
| **Total** | **254** | **25.4** | **$76** |

Note: High-volume deployments (1B+ decisions/day) will scale linearly. Use aggregation for Tier 1 to further reduce costs.

### 6.4 Cost Control Mechanisms

| Mechanism | When to Apply | Impact |
|-----------|---------------|--------|
| Reduce sampling rate | Budget exceeded by >20% | Less forensic detail |
| Increase aggregation window | High volume, low risk | Loss of per-event granularity |
| Shorten retention | Compliance allows | Historical data loss |
| Move to colder storage | After 30 days | Higher retrieval latency |

## 7. Emergency Override (Extends Spec 15)

### 7.1 Justification Code Matrix

| Code | Description | Auto-Approve Roles | Max Duration | Post-Review Required |
|------|-------------|-------------------|--------------|----------------------|
| `LIFE_SAFETY` | Imminent risk to human life | SecurityLead, OnCallEngineer | 1 hour | Yes (24h) |
| `LEGAL_COMPLIANCE` | Court order or legal obligation | LegalTeam | 24 hours | Yes (7 days) |
| `SYSTEM_RECOVERY` | Restoring critical system | SecurityLead, EngineeringDirector | 4 hours | Yes (48h) |
| `OTHER` | Any other reason | Executive | 1 hour | Yes (24h) |

### 7.2 Override Token Constraints

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Maximum validity | 1 hour | Limits blast radius |
| Maximum uses | 1 (default), 5 (with approval) | Prevents abuse |
| Action binding | Required | Cannot override different action |
| Resource binding | Required | Cannot override different resource |
| Agent binding | Required | Cannot be used by other agents |

### 7.3 Override Audit Requirements

Every override MUST capture:

```json
{
  "override_id": "...",
  "timestamp": "...",
  "requesting_agent": "...",
  "approver": "...",
  "justification_code": "...",
  "justification_text": "...",
  "original_decision": "...",
  "overridden_decision": "...",
  "action": {...},
  "resource": "...",
  "valid_from": "...",
  "valid_until": "...",
  "used_at": "...",
  "revoked_at": "..."
}
```

### 7.4 Override Abuse Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Overrides per agent per day | 5 | Alert, recertify agent |
| Overrides per approver per day | 10 | Alert, review approver |
| Same justification code usage | 100/day | Review if pattern indicates abuse |
| Consecutive overrides | 3 for same action | Require executive approval |

## 8. Monitoring & Alerting Requirements

### 8.1 Required Metrics

| Category | Metrics | Collection Interval |
|----------|---------|---------------------|
| Performance | p50/p95/p99 latency, throughput | 10 seconds |
| Errors | error rate by type, by service | 10 seconds |
| Propagation | revocation latency, cache invalidation time | 1 second |
| Conflicts | policy conflicts, zone conflicts | 1 minute |
| Overrides | override count by code, by approver | 1 minute |
| Storage | bytes stored, cost estimate | 1 hour |
| Availability | uptime, failover events | 1 minute |

### 8.2 Alert Severity Mapping

| Severity | Response Time | Examples |
|----------|---------------|----------|
| SEV-1 (Critical) | 5 minutes | PDP unavailable, revocation propagation >5s |
| SEV-2 (High) | 15 minutes | Error rate >5%, override abuse detected |
| SEV-3 (Medium) | 2 hours | Latency >2x baseline, policy conflict detected |
| SEV-4 (Low) | Next business day | Storage cost >budget, recertification due |

### 8.3 Dashboards

Implementations SHOULD provide dashboards for:

- **Operational Health** — Latency, throughput, error rates by service
- **Propagation Status** — Revocation latency, stale list percentage
- **Policy Conflicts** — Conflicts by zone, resolution outcomes
- **Override Tracking** — Override count by code, approver, agent
- **Storage Economics** — Bytes stored, cost trend, sampling rates

## 9. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
