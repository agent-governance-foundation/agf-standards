# Specification 05: Revocation and Branch Cut Model

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.3

## 1. Introduction

Revocation is the ability to invalidate a delegation before its expiration. This specification defines the revocation list format, branch cut semantics, distribution mechanisms, and bounded propagation guarantees.

## 2. Core Principle

**Revocation targets authority, not identity.**

When a delegation is revoked, the authority it granted is removed. The identity of the agent remains valid; only the specific delegation path is severed.

## 3. The Branch Cut Model

### 3.1 Tree Representation

Delegations form a tree:

```
             Alice (root)
             /           \
         del_001        del_002
         /     \             \
     Agent A  Agent B      Agent C
       /
  del_003   del_004
     |          |
  Agent D    Agent E
```

### 3.2 Cutting a Branch

When `del_001` is revoked, everything below it becomes invalid:

```
             Alice (root)
             /           \
         del_001✗       del_002
         /     \             \
     Agent A✗ Agent B✗    Agent C
       /
  del_003✗  del_004✗
     |          |
  Agent D✗   Agent E✗
```

Agents A, B, D, E lose authority. Agent C retains authority (different branch).

### 3.3 Algorithm

```python
def is_authorized(delegation_id, revocation_set):
    # Check if this delegation or any ancestor is revoked
    current = delegation_id
    while current:
        if current in revocation_set:
            return False
        current = get_parent(current)
    return True
```

## 4. Revocation List Format

### 4.1 Structure

```json
{
  "version": "1",
  "issued_at": 1735603200,
  "valid_until": 1735689600,
  "issuer": "did:agf:acme:security-team",
  "revocations": [
    {
      "delegation_id": "del_7f3e9a2b",
      "revoked_at": 1735603300,
      "reason": "compromised",
      "revoked_by": "did:agf:acme:alice"
    },
    {
      "delegation_id": "del_9c2d8f1e",
      "revoked_at": 1735603456,
      "reason": "mission_complete",
      "revoked_by": "did:agf:acme:workflow-orchestrator"
    }
  ],
  "signature": "base64..."
}
```

### 4.2 Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | List format version |
| `issued_at` | number | Yes | Creation timestamp |
| `valid_until` | number | Yes | Expiration timestamp |
| `issuer` | string | Yes | Entity that issued this list |
| `revocations` | array | Yes | List of revoked delegations |
| `signature` | string | Yes | Signature over entire list |

### 4.3 Revocation Entry

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `delegation_id` | string | Yes | The `jti` of the revoked delegation |
| `revoked_at` | number | Yes | When revocation occurred |
| `reason` | string | Yes | `compromised`, `superseded`, `mission_complete`, `policy_change` |
| `revoked_by` | string | Yes | DID of revoking entity |

### 4.4 List Size Limits

- Maximum entries per list: 10,000 (default)
- Maximum list size: 10 MB

When the limit is exceeded, the issuer MUST create a new list version and archive the old list. Verifiers MUST check both the current and archived lists. The `valid_until` of the current list SHOULD be shortened to force more frequent refreshes.

**Example versioned list:**

```json
{
  "version": "2",
  "prev_version": "1",
  "prev_list_url": "https://acme.com/revocations-v1.json",
  "issued_at": 1735603200,
  "valid_until": 1735606800,
  "revocations": [...],
  "signature": "base64..."
}
```

## 5. Revocation Distribution

### 5.1 Pull Model (Default)

Verifiers periodically fetch revocation lists from well-known URLs:

```
https://{domain}/.well-known/revocations.json
```

### 5.2 Push Model (Optional)

For low-latency requirements, domain authorities can push revocation updates via:

- Webhook
- Pub/sub (Redis, Kafka, NATS)
- gRPC stream

### 5.3 Caching

Revocation lists SHOULD be cached with TTL based on `valid_until`. Verifiers MUST NOT use a list past its `valid_until`.

### 5.4 Stale List Handling

If the revocation list is stale (`valid_until < current_time`):

1. Attempt to fetch a fresh list (retry up to 3 times with exponential backoff)
2. If fetch fails, apply the staleness policy based on how old the list is:

| Staleness | Behavior |
|-----------|----------|
| > 0s but ≤ 3600s (1 hour) | Apply −20 trust penalty; decisions proceed at their normal outcome |
| > 3600s but ≤ 86400s (1–24 hours) | Apply −20 trust penalty; decision outcome capped at `ALLOW_WITH_CAUTION` regardless of risk score |
| > 86400s (24 hours) | **REJECT** — list too stale to rely upon |

The cap to `ALLOW_WITH_CAUTION` in the 1–24 hour window prevents high-risk actions from receiving an `ALLOW` outcome while revocation state is uncertain, without completely halting operations.

The `max_stale_seconds` configuration controls the REJECT threshold (default: 86400). Operators in high-security environments SHOULD reduce this to 3600.

### 5.5 Bounded Propagation Guarantees

Revocation propagation MUST meet these latency targets:

| Propagation Path | Max Target | P99 Target | Action if Exceeded |
|------------------|------------|------------|-------------------|
| Issuance → Global Registry | 500 ms | 200 ms | Retry, escalate |
| Global → Domain | 1 second | 500 ms | Retry, escalate to on-call |
| Domain → Local Cache | 5 seconds | 2 seconds | Fall back to direct verification |
| Local Cache invalidation | 500 ms | 200 ms | Agent re-verifies before next action |

**Propagation window handling:**

If an agent acts during the propagation window (after revocation but before cache invalidation):

| Action Timing | Behavior |
|---------------|----------|
| Within propagation window | `DENY` with `propagation_window_hit: true` in audit |
| After propagation window | `DENY` normally |

Audit logs MUST record the propagation delay for forensic analysis.

## 6. Expiration by Default

### 6.1 Principle

Permanent permissions are mistakes waiting to happen. Every delegation MUST have an explicit expiration.

### 6.2 Recommended Lifetimes

| Use Case | Recommended Lifetime |
|----------|----------------------|
| Interactive session | 1–8 hours |
| Build job | 1–24 hours |
| Data pipeline | 1–7 days |
| Long-running service | 30–90 days (requires renewal) |

### 6.3 Renewal

Expired delegations cannot be renewed. A new delegation must be issued.

## 7. Example: Branch Cut in Action

### 7.1 Initial State

```
Delegations:
  del_root: Alice → Agent A  (scope: read_calendar)
  del_a1:   Agent A → Agent B (scope: read_calendar)
  del_a2:   Agent A → Agent C (scope: read_calendar)
  del_b1:   Agent B → Agent D (scope: read_calendar)
```

### 7.2 Revocation Request

Security revokes `del_a1` (Agent A's delegation to Agent B).

### 7.3 Result

- **Agent B:** Loses authority
- **Agent D:** Loses authority (branch cut)
- **Agent A:** Retains authority
- **Agent C:** Retains authority (different branch)

### 7.4 Audit Log Entry

```json
{
  "timestamp": 1735603456,
  "event": "REVOCATION",
  "delegation_id": "del_a1",
  "reason": "compromised",
  "revoked_by": "did:agf:acme:security-bot",
  "affected": ["del_a1", "del_b1"],
  "branch_cut": true,
  "propagation_estimate_ms": 250
}
```

## 8. Security Considerations

### 8.1 Revocation List Integrity

Revocation lists MUST be signed to prevent tampering. Verifiers MUST verify the signature before use.

### 8.2 Timeliness

Short `valid_until` windows force frequent refreshes, reducing the window of stale data.

### 8.3 Denial of Service

Attackers could flood revocation lists with entries. Implement rate limiting and list size limits (default: 10,000 entries per list, 10 MB max). When limits are exceeded, the issuer MUST rotate to a new list version (see Section 4.4).

### 8.4 Emergency Revocation

For critical incidents (root key compromise, widespread breach), implement the following emergency procedure:

**Immediate actions (first 5 minutes):**
1. Halt all new decisions: PDPs return `DENY` with code `EMERGENCY_HALT`
2. Revoke affected delegations using the bulk revocation API
3. If root trust anchor is compromised, notify the global registry

**Short-term actions (first hour):**
1. Rotate compromised keys (see Spec 09 — emergency rotation bypasses the normal grace period)
2. Re-issue critical delegations from known-good backups
3. Notify cross-domain partners if the compromise affects federated chains

**Long-term actions (within 24 hours):**
1. Complete an incident report (root cause, impact, preventive measures)
2. Audit all decisions made during the compromise window
3. Review and update emergency procedures as needed

A formal emergency procedures specification will be published in a future version.

### 8.5 Concurrent Revocation

When two or more processes attempt to revoke overlapping subtrees simultaneously, the following rules apply:

**Invariant:** Revocation is additive and permanent. A delegation that is revoked remains revoked regardless of the order in which concurrent operations complete.

**Implementation requirement:** The revocation store MUST be append-only. No revocation entry may be deleted or overwritten. This eliminates write-write conflicts: two processes adding entries for the same `delegation_id` produce the same final state.

**Race condition: same delegation revoked twice**

If two processes concurrently revoke the same `delegation_id`, the result is identical to a single revocation. The second write is a no-op on an append-only store. Both operations SHOULD succeed without error.

**Race condition: parent and child revoked simultaneously**

If process A revokes `del_parent` and process B concurrently revokes `del_child` (a descendant of `del_parent`):

- Both revocations take effect independently
- The branch-cut algorithm (§3.3) traverses ancestors, so `del_child` is invalid via two independent paths: its own entry and `del_parent`'s entry
- No special handling is required; the additive model resolves this correctly regardless of write order

**Version counter safety:** Revocation list version counters (§4.4) SHOULD use optimistic concurrency control (e.g., compare-and-swap) to prevent lost updates when multiple writers race to increment the version. A failed CAS MUST cause the writer to retry with the latest version rather than overwrite it.

### 8.6 Propagation Monitoring

Implementations MUST monitor propagation latency and alert when exceeding targets:

```yaml
propagation_monitoring:
  metrics:
    - propagation_latency_ms (histogram)
    - propagation_window_hits (counter)
    - stale_list_encounters (counter)
  alert_thresholds:
    propagation_latency_p99 > 1000ms: SEV-3
    propagation_latency_p99 > 5000ms: SEV-2
    stale_list_encounters > 10/hour: SEV-3
```

## 9. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
