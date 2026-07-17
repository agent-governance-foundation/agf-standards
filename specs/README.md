# Agent Governance Foundation — Specifications

This directory contains all technical specifications for the Agent Governance infrastructure.

## Specification Index

All specifications in this directory are Working Drafts. See each spec's own status banner for details. The layering below is normative per [Spec 00 §2](00-aap-core.md#2-layering-model): every spec's banner carries a `**Layer:**` line matching one of the five groupings.

### Kernel

The normative kernel: the six objects every conformant implementation MUST support, their lifecycle, and the correlation rules that bind them into an auditable record.

| # | Title | Status |
|---|-------|--------|
| [00](00-aap-core.md) | AAP-Core — Normative Kernel | Working Draft |

### Core formats

The AGF wire serializations of the kernel objects; MUST be implemented to claim *AGF* conformance.

| # | Title | Status |
|---|-------|--------|
| [01](01-delegation-token.md) | Delegation Token Format | Working Draft |
| [02](02-delegation-chain.md) | Delegation Chain Semantics | Working Draft |
| [05](05-revocation-branch-cut.md) | Revocation and Branch Cut Model | Working Draft |
| [06](06-policy-model.md) | Policy Model and Versioning | Working Draft |
| [07](07-audit-trail.md) | Audit Trail and Decision Provenance | Working Draft |
| [08](08-identity-registry.md) | Identity Registry and DID Resolution | Working Draft |
| [09](09-key-management.md) | Key Management and Rotation | Working Draft |
| [10](10-api-protocol.md) | API Protocol | Working Draft |
| [25](25-canonical-delegation-serialization.md) | Canonical Delegation Serialization (`AGF-C14N-1.0`) | Working Draft |

### Profiles

Domain and policy layers over the kernel — trust zones, risk layers, human oversight, sector controls, and cross-organization trust (Specs 24, 26, 27, 28) — each OPTIONAL and declaring its own conformance target.

| # | Title | Status |
|---|-------|--------|
| [03](03-trust-zones.md) | Trust Zones (Local, Domain, Global) | Working Draft |
| [04](04-risk-layers.md) | Risk Layers (Inherent, Environmental, Trust) | Working Draft |
| [12](12-emergency-procedures.md) | Emergency Procedures | Working Draft |
| [13](13-privacy-selective-disclosure.md) | Privacy and Selective Disclosure | Working Draft |
| [14](14-pre-deployment-governance.md) | Pre-Deployment Governance | Working Draft |
| [15](15-human-oversight-escalation.md) | Human Oversight & Escalation | Working Draft |
| [16](16-multi-agent-coordination.md) | Multi-Agent Coordination | Working Draft |
| [17](17-behavioral-monitoring-drift.md) | Behavioral Monitoring & Drift | Working Draft |
| [18](18-regulatory-compliance-mapping.md) | Regulatory Compliance Mapping | Working Draft |
| [24](24-trust-summary-format.md) | Trust Summary Format (`AGF-TS-1.0`) | Working Draft |
| [26](26-trust-relay-protocol.md) | Trust Relay Protocol (`AGF-TRP-1.0`) | Working Draft |
| [27](27-global-trust-registry-protocol.md) | Global Trust Registry Protocol (`AGF-GTR-1.0`) | Working Draft |
| [28](28-federation-revocation-sync.md) | Federation Revocation Sync | Working Draft |

### Adapters

Transport translation into kernel objects — MCP, A2A, HTTP/REST — without redefining them.

| # | Title | Status |
|---|-------|--------|
| [21](21-protocol-adapters.md) | Protocol Adapters (MCP Gateway) | Working Draft |
| [22](22-a2a-protocol-adapter.md) | Protocol Adapters (A2A Gateway) | Working Draft |
| [23](23-http-protocol-adapter.md) | Protocol Adapters (HTTP/REST Gateway) | Working Draft |

### Operational

Conformance testing, runbooks, and production-reality constraints that support implementations but sit outside the normative kernel/profile/adapter layering.

| # | Title | Status |
|---|-------|--------|
| [11](11-conformance.md) | Conformance Test Suite | Working Draft |
| [19](19-operational-runbooks.md) | Operational Runbooks | Working Draft |
| [20](20-operational-reality.md) | Operational Reality | Working Draft |

**Supporting documents:**

| Document | Description |
|----------|-------------|
| [Integration Guide](../adoption/integration-guide.md) | Migrating from existing IAM (Okta, Azure AD, LDAP) |
| [Authorization Flow](../authorization-flow.md) | Complete end-to-end walkthrough |

## Reading Order

For new readers, start with **[Spec 00 — AAP-Core](00-aap-core.md)** (kernel — read this before anything else), then the **[Authorization Flow](../authorization-flow.md)** document, which walks through the complete end-to-end picture before diving into individual specs.

Then read the specs in this order:

1. [01 — Delegation Token Format](01-delegation-token.md) — The basic building block
2. [02 — Delegation Chain Semantics](02-delegation-chain.md) — How tokens chain together
3. [05 — Revocation and Branch Cut Model](05-revocation-branch-cut.md) — How authority is revoked
4. [07 — Audit Trail and Decision Provenance](07-audit-trail.md) — How decisions are proven
5. [03 — Trust Zones](03-trust-zones.md) — Local, Domain, Global architecture
6. [04 — Risk Layers](04-risk-layers.md) — Inherent, environmental, and trust risk
7. [06 — Policy Model](06-policy-model.md) — Rego policies and versioning

Then explore the rest based on your area (core formats, profiles, adapters, and operational documents alike):

- **Identity/keys:** [08](08-identity-registry.md), [09](09-key-management.md)
- **APIs:** [10](10-api-protocol.md)
- **Operations:** [11](11-conformance.md), [12](12-emergency-procedures.md), [19](19-operational-runbooks.md)
- **Privacy/compliance:** [13](13-privacy-selective-disclosure.md), [18](18-regulatory-compliance-mapping.md)
- **Governance/lifecycle:** [14](14-pre-deployment-governance.md), [15](15-human-oversight-escalation.md), [16](16-multi-agent-coordination.md), [17](17-behavioral-monitoring-drift.md)
- **Protocol adapters:** [21](21-protocol-adapters.md), [22](22-a2a-protocol-adapter.md), [23](23-http-protocol-adapter.md)
- **Cross-org trust:** [24](24-trust-summary-format.md), [25](25-canonical-delegation-serialization.md), [26](26-trust-relay-protocol.md), [27](27-global-trust-registry-protocol.md), [28](28-federation-revocation-sync.md)

## Versioning

Specifications use semantic versioning:

- **Major** — Incompatible changes to core semantics
- **Minor** — New features, backward compatible
- **Patch** — Clarifications, editorial fixes

**Current versions:** All specs are individually versioned; most are at 0.1.0 (initial public working draft), though some (e.g. Specs 05 and 11) have advanced past that as they matured. See each specification file's own banner for its current version, and [GOVERNANCE.md](../GOVERNANCE.md) for the versioning and maturity rules.

## Contributing

Editorial fixes are welcome as direct pull requests; substantive (normative) changes go through the [RFC process](../rfcs/README.md). See [CONTRIBUTING.md](../CONTRIBUTING.md).

## License

[Apache 2.0](../LICENSE)
