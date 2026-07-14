# Specification 12: Emergency Procedures

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Profile  

## 1. Introduction

Despite best efforts, emergencies occur. This specification defines procedures for responding to critical incidents: key compromise, registry breach, widespread delegation abuse, and disaster recovery.

## 2. Incident Severity Levels

| Level | Description | Examples | Response Time |
|-------|-------------|----------|---------------|
| SEV-3 | Minor incident, limited impact | Single agent key compromise, testing misconfiguration | 24 hours |
| SEV-2 | Moderate incident, contained | Domain key compromise, revocation list corruption | 4 hours |
| SEV-1 | Severe incident, widespread impact | Root key compromise, registry breach, mass delegation abuse | Immediate (15 min) |

## 3. Emergency Revocation

### 3.1 Single Delegation Revocation (SEV-3)

Normal process via revocation API:

```bash
POST /v1/revocations
{
  "delegation_id": "del_abc123",
  "reason": "compromised"
}
```

Propagation: Standard TTL (up to 5 minutes).

### 3.2 Bulk Revocation by Issuer (SEV-2)

When an entire issuer's delegations must be revoked:

```json
POST /v1/revocations/bulk
{
  "issuer": "did:agf:acme:agent:compromised",
  "reason": "key_compromise",
  "revoke_descendants": true
}
```

Propagation: Immediate push to all domain PDPs (bypass TTL).

### 3.3 Emergency Halt (SEV-1)

When the entire domain is compromised:

**Step 1: Halt all new decisions**

```json
POST /v1/admin/halt
{
  "reason": "root_key_compromise",
  "estimated_duration_minutes": 60,
  "notify_admins": ["security@acme.com", "oncall@acme.com"]
}
```

All PDPs return `DENY` with code `EMERGENCY_HALT` until lifted.

**Step 2: Revoke root trust anchor**

```json
POST /v1/global/revoke-anchor
{
  "domain": "acme.com",
  "reason": "compromised",
  "notify_global_registry": true
}
```

**Step 3: Rotate root keys**

See Spec 09 for key rotation. Emergency rotation bypasses the normal grace period.

**Step 4: Restore services**

```json
POST /v1/admin/resume
{
  "verification_token": "..."
}
```

## 4. Key Compromise Response

### 4.1 Agent Key Compromise (SEV-3)

1. Revoke the specific delegation(s) signed with the compromised key
2. Revoke the agent's verification key (Spec 08)
3. Issue new key to agent
4. Re-issue necessary delegations

### 4.2 Domain Key Compromise (SEV-2)

1. Immediately revoke all delegations signed by the compromised key
2. Revoke the domain's verification key from identity registry
3. Generate new domain key pair (HSM required)
4. Update domain DID document
5. Notify all cross-domain partners
6. Re-issue all active delegations (may be automated)

### 4.3 Root Key Compromise (SEV-1)

Root keys are stored in HSMs with multi-party authorization. Compromise is unlikely but possible.

**Procedure:**

1. Invoke emergency halt (Section 3.3)
2. Convene security committee (minimum 3 members)
3. Physically audit HSM access logs
4. Generate new root key pair in new HSM
5. Update global trust anchors
6. Re-issue all domain trust anchors
7. Increment global revocation list version (invalidates all previous)
8. Resume services

## 5. Registry Breach Response

### 5.1 Detection

Signs of registry breach:

- Unexpected DID document changes
- New DIDs from unauthorized controllers
- Failed signature verifications from previously valid issuers

### 5.2 Response (SEV-1)

1. **Immediate:** Take registry offline (read-only mode)
2. **Verify:** Reconstruct correct state from audit logs and backups
3. **Revoke:** Invalidate all DIDs issued during breach window
4. **Notify:** All affected parties (cross-domain partners, regulators if required)
5. **Restore:** From last known good backup before breach
6. **Audit:** Full security review
7. **Resume:** With enhanced monitoring

### 5.3 Recovery Time Objective (RTO)

| Severity | Target |
|----------|--------|
| SEV-3 | 24 hours |
| SEV-2 | 4 hours |
| SEV-1 | 1 hour (halt) / 24 hours (full recovery) |

## 6. Disaster Recovery

### 6.1 Service Failure

If a PDP or trust evaluator fails:

- Clients retry with exponential backoff (max 30 seconds)
- After 3 failures, fall back to local cache (if available) with `ALLOW_WITH_CAUTION`
- All fallback decisions are marked with `emergency_fallback: true` in audit artifacts

### 6.2 Complete Outage

If the entire domain authority is unavailable:

- Agents operate in degraded mode using local cache
- Local cache TTL reduced to 15 minutes
- New delegations cannot be issued
- All decisions logged locally for later sync
- Upon restoration, sync local logs to audit service

### 6.3 Backup and Restore

| Component | Backup Frequency | Retention | Restore Method |
|-----------|-----------------|-----------|----------------|
| Identity registry | Daily | 30 days | Full restore from backup |
| Revocation lists | Every change | 90 days | Replay from event log |
| Audit artifacts | Continuous | 7+ years | Immutable storage (S3, etc.) |
| Policies | Every commit | Indefinite | Git reflog |

## 7. Communication Plan

### 7.1 Internal Notification

| Severity | Notification Method | Audience |
|----------|---------------------|----------|
| SEV-3 | Slack channel, email | Security team, affected team |
| SEV-2 | SMS + email + Slack | Security team, engineering leadership |
| SEV-1 | SMS + phone call + email | Executives, security, legal, PR |

### 7.2 External Notification

For SEV-1 incidents affecting cross-domain trust:

- Email to all cross-domain partners
- Post to foundation status page
- Update global trust registry with incident marker
- Regulatory notification if required (data breach laws)

## 8. Incident Report Template

After resolution, produce an incident report using this template:

```
# Incident Report: [ID]

Date:     YYYY-MM-DD
Severity: SEV-1/2/3
Duration: Start → End (total minutes)
Impact:   [Number of agents, delegations, users affected]

## Timeline
- T+0:   [Detection method]
- T+5:   [Initial response]
- T+30:  [Containment]
- T+60:  [Recovery started]
- T+120: [Services restored]

## Root Cause
[What happened, why, how]

## Resolution
[Steps taken to fix]

## Preventive Measures
- [Item 1]
- [Item 2]

## Lessons Learned
[What went well, what didn't]
```

## 9. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
