# Specification 17: Behavioral Monitoring & Drift

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.0

## 1. Introduction

Agents operate in changing environments. Their behavior can drift from original intent over time. This specification defines behavioral baseline profiling, anomaly detection, drift alerting, and periodic recertification.

## 2. Core Principle

**Trust decays; behavior drifts. Both must be measured.**

What an agent was authorized to do yesterday may not match what it actually does today. Ongoing monitoring detects divergence before it becomes an incident.

## 3. Behavioral Baseline

### 3.1 Baseline Establishment

Every agent MUST establish a behavioral baseline within the first 30 days of deployment.

```json
POST /v1/agents/{did}/baseline
{
  "observation_window_days": 30,
  "metrics": [
    "action_volume_per_hour",
    "action_type_distribution",
    "resource_access_pattern",
    "time_of_day_activity",
    "delegation_depth_used",
    "average_trust_score",
    "escalation_frequency"
  ]
}
```

### 3.2 Baseline Output

```json
{
  "agent_id": "did:agf:acme:agent:procurement-bot",
  "baseline_id": "bsl_1735603300_a1b2",
  "established_at": 1735603300,
  "metrics": {
    "action_volume_per_hour": {"mean": 42, "stddev": 8, "p99": 65},
    "action_type_distribution": {
      "read:po":    0.70,
      "create:po":  0.25,
      "approve:po": 0.05
    },
    "resource_access_pattern": {
      "purchase_orders/*": 0.95,
      "vendors/*":         0.05
    },
    "time_of_day_activity": {
      "09:00-17:00": 0.85,
      "17:00-21:00": 0.15
    },
    "delegation_depth_used": {"mean": 2.1, "stddev": 0.5},
    "average_trust_score": 87,
    "escalation_frequency": {"mean_per_day": 0.2, "stddev": 0.1}
  }
}
```

## 4. Drift Detection

### 4.1 Detection Methods

| Method | Threshold | Action |
|--------|-----------|--------|
| Statistical deviation | > 3 standard deviations from baseline | Alert |
| Trend detection | 5 consecutive days trending away | Alert + recertification required |
| Sudden change | > 50% change in 1 hour | High-severity alert |
| New behavior | Action type never seen in baseline | Alert + review |

### 4.2 Drift Alert

```json
{
  "alert_id": "dft_1735603300_c3d4",
  "agent_id": "did:agf:acme:agent:procurement-bot",
  "timestamp": 1735603300,
  "severity": "MEDIUM",
  "drift_type": "statistical",
  "metric": "action_volume_per_hour",
  "baseline_mean": 42,
  "baseline_stddev": 8,
  "current_value": 71,
  "deviations": 3.6,
  "action": "ALERT"
}
```

## 5. Recertification

### 5.1 Recertification Schedule

| Agent Risk Tier | Recertification Frequency |
|-----------------|--------------------------|
| Tier 1 | Annual |
| Tier 2 | Semi-annual |
| Tier 3 | Quarterly |

### 5.2 Recertification Trigger Events

Recertification MUST also occur when:

- Drift alert of severity MEDIUM or higher
- Policy change affecting agent's scope
- Agent's delegation chain changes significantly (depth, `max_depth`)
- Security incident involving similar agents
- Organizational change (merger, acquisition, reorg)

### 5.3 Recertification Workflow

```
Recertification Trigger
        │
        ▼
┌─────────────────────────────────────────────┐
│ Generate recertification request            │
│ - Current behavior vs baseline              │
│ - Drift events since last cert              │
│ - Open alerts                               │
└───────────────┬─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────┐
│ Assigned to agent owner + security          │
└───────────────┬─────────────────────────────┘
                │
        ┌───────┴───────┐
        ▼               ▼
┌──────────────┐  ┌──────────────┐
│ Approve      │  │ Request      │
│ (certified)  │  │ Changes      │
└──────┬───────┘  └──────┬───────┘
       ▼                 ▼
┌──────────────┐  ┌──────────────┐
│ Update       │  │ Update scope,│
│ valid_until  │  │ policies, or │
│              │  │ decommission │
└──────────────┘  └──────────────┘
```

### 5.4 Recertification Record

```json
{
  "recertification_id": "rcrt_1735603300_e5f6",
  "agent_id": "did:agf:acme:agent:procurement-bot",
  "previous_valid_until": 1767139200,
  "new_valid_until": 1798675200,
  "reviewer": "did:agf:acme:sec-lead",
  "findings": "Agent behavior stable. No drift alerts. Approve recertification.",
  "approved_at": 1735603300,
  "next_recertification_due": 1798675200
}
```

## 6. Continuous Monitoring Requirements

| Metric | Collection Frequency | Retention |
|--------|---------------------|-----------|
| Action volume | Real-time | 90 days |
| Action types | Real-time | 365 days |
| Resource access | Real-time | 90 days |
| Trust score | Per decision | 365 days |
| Escalations | Per event | 7 years |
| Drift alerts | Per detection | 7 years |

## 7. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
