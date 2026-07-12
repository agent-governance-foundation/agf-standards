# Specification 18: Regulatory Compliance Mapping

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** None

## 1. Introduction

Agent governance must align with existing regulatory frameworks. This specification maps AGF specifications to NIST AI RMF, ISO/IEC 42001, and EU AI Act requirements.

## 2. Core Principle

**Compliance is not a feature; it is a property of the system.**

Organizations should not have to rebuild governance for each regulation. A single AGF implementation satisfies multiple frameworks.

## 3. NIST AI Risk Management Framework (AI RMF) Mapping

| NIST AI RMF Function | AGF Specification | How AGF Addresses It |
|---------------------|------------------|--------------------|
| GOVERN | Spec 14, 15, 18 | Pre-deployment assessment, human oversight, compliance mapping |
| MAP | Spec 14 §3 (Risk tiers) | Risk classification before deployment |
| MEASURE | Spec 17 (Behavioral monitoring) | Continuous drift detection, baseline profiling |
| MANAGE | Spec 05 (Revocation), Spec 12 (Emergency) | Runtime risk response, incident handling |

### 3.1 NIST AI RMF Crosswalk

| NIST Requirement | AGF Section |
|-----------------|-------------|
| AI risk identification | Spec 14 §4 (Impact assessment) |
| AI risk categorization | Spec 14 §3 (Risk tiers) |
| AI risk prioritization | Spec 04 (Risk layers) |
| AI risk measurement | Spec 17 (Behavioral monitoring) |
| AI risk management | Spec 05 (Revocation), Spec 12 (Emergency) |
| Documentation and traceability | Spec 07 (Audit trail) |
| Third-party risk | Spec 03 §6 (Global zone, cross-domain) |
| Human-AI configuration | Spec 15 (Human oversight) |

## 4. ISO/IEC 42001:2023 (AI Management Systems) Mapping

| ISO 42001 Clause | AGF Specification | How AGF Addresses It |
|-----------------|------------------|--------------------|
| 5.1 Leadership | Spec 14 §5 (Deployment gates) | Executive approval for Tier 3 |
| 6.1 Risk assessment | Spec 14 §4 (Impact assessment) | Structured pre-deployment analysis |
| 7.1 Resources | Spec 09 (Key management) | Identity and key infrastructure |
| 8.1 Operational planning | Spec 06 (Policy model) | Policy-driven authorization |
| 8.2 AI system development | Spec 01–13 (Core runtime) | Complete authorization framework |
| 8.3 AI system deployment | Spec 14 (Pre-deployment) | Deployment gates and approvals |
| 8.4 AI system monitoring | Spec 17 (Behavioral monitoring) | Drift detection, recertification |
| 8.5 AI system maintenance | Spec 05 (Revocation), Spec 09 (Key rotation) | Ongoing authority management |
| 8.6 AI system decommission | Spec 14 §7 (Decommissioning) | Structured removal |
| 9.1 Performance evaluation | Spec 11 (Conformance) | Compliance testing |
| 10.1 Continual improvement | Spec 17 §5 (Recertification) | Periodic review cycles |

## 5. EU AI Act Mapping

### 5.1 Risk Classifications

| EU AI Act Risk Level | AGF Risk Tier | AGF Section |
|---------------------|--------------|-------------|
| Minimal risk | Tier 1 | Spec 14 §3 |
| Limited risk | Tier 2 | Spec 14 §3 |
| High risk | Tier 3 | Spec 14 §3 |
| Unacceptable risk | N/A (prohibited) | Not applicable |

### 5.2 High-Risk AI System Requirements (EU AI Act Articles 9–15)

| EU AI Act Requirement | AGF Section | Compliance Evidence |
|----------------------|-------------|-------------------|
| Risk management system (Art 9) | Spec 14 (Pre-deployment) | Impact assessment document |
| Data governance (Art 10) | Spec 08 (Identity registry) | Agent identity provenance |
| Technical documentation (Art 11) | Spec 07 (Audit trail) | Decision artifacts |
| Record-keeping (Art 12) | Spec 07 (Audit trail) | Immutable decision logs |
| Transparency (Art 13) | Spec 07 (Artifact schema) | Self-contained proofs |
| Human oversight (Art 14) | Spec 15 (Human oversight) | HITL/HOTL/HIC modes |
| Accuracy, robustness, security (Art 15) | Spec 11 (Conformance) | Test suite certification |

### 5.3 Conformity Assessment (EU AI Act Article 43)

AGF conformance level (Spec 11 §2) maps to EU AI Act conformity routes:

| AGF Conformance Level | EU AI Act Route | Applicable to |
|----------------------|----------------|---------------|
| Level 1 | Self-assessment | Limited risk |
| Level 2 | Third-party assessment | High-risk (non-critical) |
| Level 3 | Notified body | High-risk (critical infrastructure) |

## 6. Other Regulatory Frameworks

| Framework | Relevance | AGF Section |
|-----------|-----------|-------------|
| GDPR (Art 22, 35) | Automated decision-making, DPIA | Spec 07 (Audit), Spec 14 (Impact assessment) |
| SOC 2 (CC7, A1) | Security monitoring, availability | Spec 17 (Monitoring), Spec 03 §4.2 (Availability) |
| HIPAA Security Rule | Access control, audit logs | Spec 01 (Delegation), Spec 07 (Audit) |
| SOX (Section 404) | Financial controls | Spec 14 (Pre-deployment), Spec 07 (Audit retention) |
| PCI DSS (Requirement 7) | Access restrictions | Spec 02 (Scope narrowing), Spec 06 (Policy) |

## 7. Compliance Report Generation

The audit service MUST support compliance report generation:

```bash
POST /v1/compliance/report
{
  "framework": "eu_ai_act",
  "agent_id": "did:agf:acme:agent:procurement-bot",
  "period_start": 1735603200,
  "period_end": 1767139200,
  "format": "pdf"
}
# Response: Compliance report with evidence links to decision artifacts.
```

The real endpoint takes a single `framework` query parameter, not the request body above, and has no PDF generation — the response is plain JSON (`report_id`, `framework`, `generated_at`, `coverage`, `controls`, `summary`). It is org-wide, not scoped to a single agent or time period, and does not carry evidence links to decision artifacts; it's a snapshot of the crosswalk's current status values.

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
