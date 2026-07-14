# Specification 14: Pre-Deployment Governance

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.0  
**Layer:** Profile  

## 1. Introduction

Before an agent receives any delegation, the organization must assess the impact of its intended authority. This specification defines the pre-deployment governance process: impact assessment, risk tiering, deployment gates, and decommissioning.

## 2. Core Principle

**Authority should be justified before it is granted.**

No agent should receive delegation without a documented assessment of what it will do, what could go wrong, and who is accountable.

## 3. Agent Risk Tiers

Every agent MUST be classified into one of three risk tiers before deployment.

| Tier | Name | Criteria | Examples | Required Reviews |
|------|------|----------|----------|-----------------|
| Tier 1 | Low Risk | Read-only, non-sensitive, no financial impact, fully reversible | Read public calendar, list files, search logs | Self-review only |
| Tier 2 | Medium Risk | Write access, moderate financial impact, some reversibility | Create draft document, approve <$1000, update ticket | Security team review |
| Tier 3 | High Risk | Delete access, high financial impact, irreversible, privileged | Delete backup, approve >$100K, delegate admin, access PII | Security + Legal + Executive review |

Risk tier determines:

- Required approval gates
- Human oversight mode (Spec 15)
- Monitoring frequency (Spec 17)
- Maximum delegation lifetime

## 4. Pre-Deployment Impact Assessment

Before any agent receives delegation, the deploying organization MUST complete an impact assessment document.

### 4.1 Required Sections

```json
{
  "agent_id": "did:agf:acme:agent:procurement-bot",
  "risk_tier": "Tier 2",
  "assessment_date": 1735603200,
  "assessed_by": "did:agf:acme:security-team",

  "intended_scope": {
    "actions": ["read:po", "create:po"],
    "resources": ["purchase_orders/*"],
    "max_financial_impact_per_action": 50000,
    "max_daily_volume": 100
  },

  "out_of_scope": [
    "modify:vendor",
    "approve:payment>50000",
    "access:employee_data"
  ],

  "risk_analysis": {
    "financial_risk": "Medium - unauthorized POs up to $50K",
    "operational_risk": "Low - POs can be reversed",
    "reputational_risk": "Low - internal system only",
    "compliance_risk": "None - no PII or regulated data"
  },

  "mitigations": [
    "Daily spend limits enforced by PDP",
    "All POs logged to audit service",
    "Manager approval for POs >$10K"
  ],

  "oversight_plan": {
    "human_review_threshold": 10000,
    "reviewer_role": "ProcurementManager",
    "escalation_timeout_seconds": 3600,
    "fallback_action": "DENY"
  },

  "decommission_plan": {
    "scheduled_end_date": 1767139200,
    "data_retention_days": 2555,
    "credential_revocation": "Automatic on end date"
  },

  "approvals": [
    {"role": "Security", "approver": "did:agf:acme:sec-lead", "status": "approved", "date": 1735603300},
    {"role": "Legal",    "approver": "did:agf:acme:legal",    "status": "approved", "date": 1735603400}
  ]
}
```

## 5. Deployment Gates

An agent MAY NOT receive delegation until all required approvals are obtained.

### 5.1 Approval Workflow

```
Request Deployment
        │
        ▼
┌───────────────┐
│ Impact        │─── Tier 1 ──▶ Auto-approve
│ Assessment    │
└───────┬───────┘
        │ Tier 2 / Tier 3
        ▼
┌───────────────┐
│ Security      │─── Deny ──▶ Reject
│ Review        │
└───────┬───────┘
        │ Approve
        ▼
┌───────────────┐
│ Legal Review  │─── (Tier 3 only)
└───────┬───────┘
        │ Approve (Tier 3)
        ▼
┌───────────────┐
│ Executive     │─── (Tier 3 only)
│ Review        │
└───────┬───────┘
        │ Approve
        ▼
┌───────────────┐
│ Delegation    │
│ Issued        │
└───────────────┘
```

### 5.2 Approval Validity

The highest-risk tier MUST recertify most often, not least — a shorter validity period for higher risk is the correct security posture.

| Tier | Approval Validity |
|------|------------------|
| Tier 1 | 365 days |
| Tier 2 | 180 days |
| Tier 3 | 90 days |

After validity expires, the agent MUST be recertified (see Spec 17 §5).

## 6. Deployment Record

Every deployment MUST create a signed deployment record stored in the audit service.

```json
{
  "deployment_id": "dep_1735603300_a1b2",
  "agent_id": "did:agf:acme:agent:procurement-bot",
  "risk_tier": "Tier 2",
  "assessment_hash": "sha256:abc123...",
  "first_delegation_id": "del_7f3e9a2b",
  "deployed_at": 1735603300,
  "deployed_by": "did:agf:acme:security-bot",
  "valid_until": 1767139200,
  "status": "active"
}
```

## 7. Decommissioning

When an agent is no longer needed or its risk tier changes:

### 7.1 Decommission Steps

1. Revoke delegations (Spec 05) — all active delegations for the agent
2. Revoke identity (Spec 08) — mark DID as revoked
3. Revoke keys (Spec 09) — add keys to revocation list
4. Archive audit records — preserve for required retention period
5. Update deployment record — `status = "decommissioned"`

### 7.2 Decommission Record

```json
{
  "decommission_id": "dec_1735689600_c3d4",
  "deployment_id": "dep_1735603300_a1b2",
  "decommissioned_at": 1735689600,
  "decommissioned_by": "did:agf:acme:sec-lead",
  "reason": "service_sunset",
  "audit_retention_until": 1798761600
}
```

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
