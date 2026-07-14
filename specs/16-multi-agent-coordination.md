# Specification 16: Multi-Agent Coordination

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Profile  

## 1. Introduction

Multiple agents may operate within the same environment, coordinate on shared tasks, or inadvertently interfere with each other. This specification defines governance for multi-agent systems: joint authorization, cross-agent policies, and emergent behavior detection.

## 2. Core Principle

**The whole may have authority that no single agent possesses.**

When agents coordinate, their combined actions may create effects — intended or unintended — that exceed individual capabilities. Governance must account for the system, not just each agent in isolation.

## 3. Joint Authorization

### 3.1 Problem

A single agent may not have sufficient authority for a high-risk action, but two agents acting together (with different permissions) might collectively satisfy the requirement.

### 3.2 Solution: Multi-Signature Delegation

```json
{
  "action": "approve:payment",
  "resource": "amount=500000",
  "required_approvals": [
    "did:agf:acme:agent:finance-bot",
    "did:agf:acme:agent:compliance-bot"
  ],
  "min_approvals": 2
}
```

Both agents must independently approve before the action proceeds.

### 3.3 Joint Authorization Token

```json
{
  "iss": "did:agf:acme:orchestrator",
  "sub": "did:agf:acme:joint:payment-approval",
  "type": "joint_authorization",
  "participants": [
    "did:agf:acme:agent:finance-bot",
    "did:agf:acme:agent:compliance-bot"
  ],
  "required_approvals": 2,
  "scope": ["approve:payment/amount=500000"],
  "exp": 1735689600
}
```

## 4. Cross-Agent Policy Evaluation

### 4.1 Policy with Agent Coordination

```rego
# Payment approval policy with multi-agent coordination
allow {
    input.action.type = "approve:payment"
    amount := parse_amount(input.action.resource)
    amount <= 10000
    input.agent_trust_score >= 70
}

allow {
    input.action.type = "approve:payment"
    amount := parse_amount(input.action.resource)
    amount > 10000
    amount <= 100000
    input.agent_trust_score >= 80
    input.coordinating_agents[_] == "did:agf:acme:agent:compliance-bot"
}

allow {
    input.action.type = "approve:payment"
    amount := parse_amount(input.action.resource)
    amount > 100000
    input.joint_approval_count >= 3
    input.coordinating_agents[_] == "did:agf:acme:agent:compliance-bot"
    input.coordinating_agents[_] == "did:agf:acme:agent:treasury-bot"
}
```

### 4.2 Agent Coordination Registry

The identity registry MUST support agent team definitions:

```json
POST /v1/identities/teams
{
  "team_id": "did:agf:acme:team:payment-approval",
  "members": [
    "did:agf:acme:agent:finance-bot",
    "did:agf:acme:agent:compliance-bot",
    "did:agf:acme:agent:treasury-bot"
  ],
  "quorum": 2,
  "policies": ["approve:payment>50000"]
}
```

## 5. Emergent Behavior Detection

### 5.1 Definition

Emergent behavior: actions or outcomes that arise from agent interactions that were not explicitly programmed or authorized by any single agent's delegation chain.

### 5.2 Detection Methods

| Method | Description | Implementation |
|--------|-------------|---------------|
| Action sequence analysis | Detect chains of actions across agents that produce a combined effect | Log analysis, pattern matching |
| Resource contention detection | Multiple agents accessing same resource in unexpected ways | Audit log correlation |
| Authority composition detection | Two agents' permissions combine to exceed any individual's scope | Policy intersection analysis |
| Anomaly correlation | Unusual patterns across agents, not just per-agent | ML-based detection |

### 5.3 Emergent Behavior Alert

```json
{
  "alert_id": "emb_1735603300_a1b2",
  "timestamp": 1735603300,
  "severity": "MEDIUM",
  "description": "Two agents sequentially modified the same critical configuration",
  "agents": [
    "did:agf:acme:agent:deployer",
    "did:agf:acme:agent:config-bot"
  ],
  "action_chain": [
    {"agent": "deployer",   "action": "read:config/production"},
    {"agent": "config-bot", "action": "write:config/production", "time_delta_seconds": 45}
  ],
  "combined_effect": "Configuration change that neither agent could do alone",
  "recommended_action": "Review if this coordination was intended"
}
```

## 6. Emergent Behavior Response

When emergent behavior is detected:

| Severity | Response |
|----------|----------|
| LOW | Log only, include in weekly review |
| MEDIUM | Alert security team, flag for human review |
| HIGH | Automatic escalation to security team, consider halting involved agents |
| CRITICAL | Emergency halt, notify on-call, preserve full audit trail |

## 7. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
