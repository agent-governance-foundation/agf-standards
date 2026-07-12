# Specification 15: Human Oversight & Escalation

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.1

## 1. Introduction

Autonomous agents operate without continuous human supervision, but humans must retain the ability to intervene. This specification defines human oversight modes, escalation thresholds, timeout handling, intervention authority, and emergency override protocols.

## 2. Core Principle

**Autonomy does not mean absence of accountability.**

Every agent must have designated humans who can monitor, approve, override, or halt its actions.

## 3. Oversight Modes

| Mode | Definition | When Used | Agent Behavior |
|------|------------|-----------|----------------|
| **Human-on-the-loop (HOTL)** | Human monitors but does not approve each action | Tier 1, routine operations | Agent acts autonomously; human reviews logs |
| **Human-in-the-loop (HITL)** | Human approves certain actions before execution | Tier 2, actions above threshold | Agent requests approval, waits for response |
| **Human-in-command (HIC)** | Human directs each action | Tier 3, irreversible actions | Agent proposes, human approves, agent executes |
| **Human-on-call (HOC)** | Human available for escalation | All tiers, anomaly detection | Agent acts, escalates if uncertainty high |

## 4. Approval Thresholds

Delegation tokens MAY include `requires_approval` constraints.

```json
{
  "scope": ["approve:payment"],
  "constraints": {
    "requires_approval": {
      "threshold": 10000,
      "approver_role": "FinanceManager",
      "timeout_seconds": 3600,
      "on_timeout": "DENY"
    }
  }
}
```

### 4.1 Approval Request Flow

```
Agent initiates action
        │
        ▼
┌─────────────────────────────────────────────┐
│ PDP evaluates: action requires approval?    │
└───────────────┬─────────────────────────────┘
                │ Yes
                ▼
┌─────────────────────────────────────────────┐
│ PDP sends approval request to approver      │
│ - Action details                            │
│ - Delegation chain                          │
│ - Risk score                                │
│ - Timeout                                   │
└───────────────┬─────────────────────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
┌──────────────┐  ┌──────────────┐
│ Approver     │  │ Timeout      │
│ approves     │  │ expires      │
└──────┬───────┘  └──────┬───────┘
       ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ ALLOW        │  │ DENY or      │
│ (agent       │  │ fallback     │
│ continues)   │  │ action       │
└──────────────┘  └──────────────┘
```

## 5. Escalation Timeout Handling

When a human does not respond within the timeout period:

| Timeout Policy | Behavior | Use Case |
|----------------|----------|----------|
| `DENY` | Action rejected, agent stops | High-risk actions |
| `ESCALATE` | Send to next-level approver | Multiple approval tiers |
| `CONTINUE_WITH_CAUTION` | Proceed but log with warning | Low-risk, time-sensitive |
| `RETRY` | Resend request with backoff | Temporary unavailability |

Example configuration:

```json
{
  "escalation_policy": {
    "levels": [
      {"role": "Manager",  "timeout_seconds": 900},
      {"role": "Director", "timeout_seconds": 600},
      {"role": "VP",       "timeout_seconds": 300}
    ],
    "final_timeout_action": "DENY"
  }
}
```

## 6. Emergency Override Protocol

### 6.1 When Override is Permitted

Emergency overrides are permitted ONLY for:

| Justification Code | Description | Requires Approval |
|--------------------|-------------|-------------------|
| `LIFE_SAFETY` | Imminent risk to human life | Pre-approved roles only |
| `LEGAL_COMPLIANCE` | Court order or legal obligation | Legal team approval |
| `SYSTEM_RECOVERY` | Restoring critical system availability | Security + Engineering |
| `OTHER` | Any other reason | Executive approval |

### 6.2 Override Request Flow

```
Agent detects need for override
        │
        ▼
┌─────────────────────────────────────────────┐
│ Agent requests override with:               │
│ - Justification code                        │
│ - Detailed reason (min 20 chars)            │
│ - Desired action                            │
│ - Requested duration (max 3600 seconds)     │
└───────────────┬─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────┐
│ Human Oversight Gateway validates:          │
│ - Justification code permitted?             │
│ - Requester has pre-approval?               │
│ - Route to appropriate approver             │
└───────────────┬─────────────────────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
┌──────────────┐  ┌──────────────┐
│ Pre-approved │  │ Needs        │
│ role         │  │ approval     │
└──────┬───────┘  └──────┬───────┘
       ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ Auto-approve │  │ Route to     │
│ (with audit) │  │ approver     │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                ▼
┌─────────────────────────────────────────────┐
│ Issue time-bounded override token           │
│ - Valid for requested duration (max 1 hour) │
│ - Single-use by default                     │
│ - Bound to specific action/resource         │
└───────────────┬─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────┐
│ Agent executes with override token          │
│ - Token expires after duration              │
│ - Token invalidated after use               │
│ - Full audit trail captured                 │
└─────────────────────────────────────────────┘
```

### 6.3 Override Token Format

```json
{
  "override_id": "ovr_1735603300_a1b2c3",
  "issued_at": 1735603300,
  "valid_until": 1735606900,
  "requesting_agent": "did:agf:acme:agent:deployer",
  "approver": "did:agf:acme:sec-lead",
  "justification_code": "SYSTEM_RECOVERY",
  "justification_text": "Database replication lag causing service degradation",
  "action": {
    "type": "execute:deployment",
    "resource": "production/database"
  },
  "max_uses": 1,
  "signature": "base64..."
}
```

### 6.4 Post-Override Requirements

| Requirement | Deadline | Action |
|-------------|----------|--------|
| Audit log entry | Immediate | Override recorded with full context |
| Post-hoc review | 24 hours | Security team reviews override |
| Justification validation | 7 days | Legal review for `LIFE_SAFETY`/`LEGAL_COMPLIANCE` |
| Trend analysis | Monthly | Report on override frequency by code |

### 6.5 Override Abuse Detection

```yaml
override_monitoring:
  metrics:
    - overrides_per_hour_by_agent
    - overrides_per_hour_by_approver
    - override_justification_distribution
  alert_thresholds:
    overrides_per_hour_by_agent > 5: SEV-3 (potential abuse)
    overrides_per_hour_by_approver > 10: SEV-2 (review approver)
    same_agent_override_within_24h > 3: SEV-3 (recertify agent)
```

## 7. Intervention Authority

### 7.1 Who Can Intervene

| Role | Can Halt Agent | Can Override Decision | Can Revoke Delegation | Can Issue Emergency Override |
|------|---------------|----------------------|----------------------|------------------------------|
| Agent Owner | Yes | No | Yes | No |
| Security Team | Yes | Yes | Yes | Yes (with approval) |
| Compliance Officer | Yes | Yes | No | No |
| On-call Engineer | Yes (emergency only) | No | Yes (emergency only) | Yes (pre-approved) |

### 7.2 Intervention Methods

| Method | Description | API Endpoint |
|--------|-------------|--------------|
| Halt agent | Stop all new decisions | `POST /v1/agents/{did}/halt` |
| Override decision | Force allow/deny for specific action | `POST /v1/decisions/override` |
| Revoke delegation | Remove authority permanently | `POST /v1/revocations` |
| Emergency halt | Global shutdown (Spec 12) | `POST /v1/admin/halt` |
| Emergency override | Time-bounded override (this spec) | `POST /v1/emergency/override` |

### 7.3 Override Record

All overrides MUST be logged:

```json
{
  "override_id": "ovr_1735603300_a1b2",
  "type": "emergency",
  "original_decision": "DENY",
  "overridden_decision": "ALLOW",
  "overridden_by": "did:agf:acme:sec-lead",
  "justification_code": "SYSTEM_RECOVERY",
  "justification_text": "...",
  "timestamp": 1735603300,
  "valid_until": 1735606900
}
```

Overrides MUST have an expiration (max: 1 hour).

## 8. Audit Requirements for Oversight

Every human interaction with the agent system MUST be audited:

- Approval requests and responses
- Timeout events
- Interventions and overrides
- Escalation paths taken
- Emergency override requests and approvals

## 9. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
