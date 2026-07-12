# Specification 19: Operational Runbooks

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None

## 1. Introduction

Specifications define what the system does. Runbooks define what humans do when things go wrong. This specification provides operational runbooks for common scenarios: revocation, key rotation, outage response, and on-call procedures.

The `agf-cli` commands in this document are illustrative — they show what a conformant operational tool could provide. Treat this document as protocol-level procedure, not a description of any particular deployment.

## 2. Core Principle

**If it's not in a runbook, it didn't happen.**

Every operational procedure must be documented, tested, and accessible to on-call engineers.

## 3. Runbook 1: Emergency Revocation

### 3.1 Trigger

- Suspected agent compromise
- Unauthorized action detected
- Key compromise notification

### 3.2 Steps

```bash
# Step 1: Identify affected delegations
agf-cli delegation list --agent did:agf:acme:agent:suspicious

# Step 2: Isolate the agent (immediate halt)
agf-cli agent halt \
  --did did:agf:acme:agent:suspicious \
  --reason "suspected_compromise"

# Step 3: Revoke all delegations from this agent
agf-cli revocation bulk \
  --issuer did:agf:acme:agent:suspicious \
  --reason "compromised"

# Step 4: Revoke agent identity
agf-cli identity revoke --did did:agf:acme:agent:suspicious

# Step 5: Verify revocation took effect
agf-cli delegation verify \
  --chain <delegation_id> \
  --expect-revoked

# Step 6: Notify affected parties
# - Security team, Agent owner, any cross-domain partners

# Step 7: Preserve evidence
agf-cli audit export \
  --agent did:agf:acme:agent:suspicious \
  --since 7d
```

### 3.3 Expected Duration

5–10 minutes.

### 3.4 Success Criteria

- Agent shows status `HALTED`
- All delegations show status `REVOKED`
- Attempted actions return `AGENT_HALTED` error

## 4. Runbook 2: Emergency Key Rotation

### 4.1 Trigger

- Key expiration approaching (< 7 days)
- Key compromise suspected
- Personnel change (key holder departed)

### 4.2 Steps

```bash
# Step 1: Generate new key pair
agf-cli key generate --algorithm ES256 --output /secure/keys/

# Step 2: Add new key to DID document
agf-cli identity key add \
  --did did:agf:acme:agent:bot \
  --key-file new-key.pub

# Step 3: Wait for propagation (2× cache TTL, default 10 minutes)
agf-cli identity resolve \
  --did did:agf:acme:agent:bot \
  --wait-for-key new-key-id

# Step 4: Start signing with new key
# Update agent configuration to use new private key.

# Step 5: Verify new key works
agf-cli delegation create \
  --issuer did:agf:acme:agent:bot \
  --key new-key

# Step 6: Remove old key after grace period
agf-cli identity key remove \
  --did did:agf:acme:agent:bot \
  --key-id old-key-id

# Step 7: Securely delete old private key
shred -u /secure/keys/old-private-key.pem
```

### 4.3 Expected Duration

15–20 minutes (including propagation wait).

## 5. Runbook 3: PDP Outage Response

### 5.1 Detection

- Health check fails: `curl https://pdp.acme.com/health` returns non-200
- Client timeouts (> 100ms)
- Alert from monitoring system

### 5.2 Steps

```bash
# Step 1: Confirm outage scope
for i in 1 2 3; do curl https://pdp-$i.acme.com/health; done

# Step 2: If partial outage, route around
# Update load balancer to exclude failed instances.

# Step 3a: If full outage — secondary region
kubectl config use-context secondary-region
kubectl scale deployment pdp --replicas=3

# Step 3b: If no secondary — degraded mode
# Agents fall back to local cache (Spec 03 §4.1)
# Ensure local cache TTL is sufficient (default 5 min)

# Step 4: Investigate root cause
kubectl logs deployment/pdp --tail=1000
kubectl top pods

# Step 5: Restore primary region
kubectl rollout restart deployment/pdp

# Step 6: Verify restored
until curl -s https://pdp.acme.com/health | grep -q "healthy"; do sleep 5; done

# Step 7: Post-incident
# Collect audit logs from degraded mode period
# Update runbook with learnings
```

### 5.3 Expected Duration

5–30 minutes depending on failover mode.

## 6. Runbook 4: On-Call Procedures

### 6.1 On-Call Rotation

| Time | Primary | Secondary |
|------|---------|-----------|
| 09:00–17:00 (weekdays) | Security Engineer | Platform Engineer |
| 17:00–09:00 (weekdays) | Platform Engineer | Security Engineer |
| Weekends | Rotating | Security Manager |

### 6.2 Alert Triage

| Alert Severity | Initial Response Time | Action |
|---------------|-----------------------|--------|
| SEV-1 (Critical) | 5 minutes | Page primary + secondary, start bridge call |
| SEV-2 (High) | 15 minutes | Page primary, acknowledge within 15 min |
| SEV-3 (Medium) | 2 hours | Ticket created, respond during business hours |
| SEV-4 (Low) | Next business day | Ticket created, no page |

### 6.3 Escalation Chain

```
Level 1: On-call Engineer (5 min)
    │ No response
    ▼
Level 2: Security Lead (15 min)
    │ No response
    ▼
Level 3: Engineering Director (30 min)
    │ No response
    ▼
Level 4: CISO / VP Engineering (60 min)
```

### 6.4 On-Call Handoff

Daily handoff at 09:00 and 17:00 local time.

Handoff checklist:

- Open incidents reviewed
- In-progress revocations documented
- Pending key rotations noted
- Outstanding drift alerts reviewed
- Runbook updates from prior shift
- Known issues communicated

## 7. Runbook 5: Post-Incident Review

### 7.1 When Required

- Any SEV-1 incident
- Any SEV-2 incident with customer impact
- Any incident involving revocation or key compromise
- Any incident lasting > 30 minutes

### 7.2 Required Participants

- Incident commander
- On-call engineer
- Security team representative
- Agent owner (if agent-related)

### 7.3 Review Template

```markdown
# Post-Incident Review: [INC-12345]

**Date:** YYYY-MM-DD
**Participants:** [Names]
**Duration:** [Start] - [End]
**Severity:** SEV-1/2/3
**Impact:** [Number of agents, actions, users affected]

## Timeline
- T+0:  [Alert received]
- T+5:  [First responder acknowledged]
- T+15: [Root cause identified]
- T+30: [Mitigation applied]
- T+45: [Services restored]

## Root Cause
[What happened, why, how]

## Detection
[How was it detected? Could it have been faster?]

## Response
[What went well, what didn't]

## Preventive Measures
- [ ] [Action item 1] (Owner: [Name], Due: [Date])
- [ ] [Action item 2] (Owner: [Name], Due: [Date])

## Runbook Updates Required
- [ ] [Update needed to Runbook X]
```

## 8. Runbook Maintenance

| Requirement | Frequency | Owner |
|-------------|-----------|-------|
| Review all runbooks | Quarterly | Security Team |
| Test emergency revocation | Monthly | Platform Team |
| Test key rotation | Monthly | Platform Team |
| Tabletop incident drill | Semi-annual | All teams |
| Update on-call rotation | Weekly | Team lead |

## 9. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
