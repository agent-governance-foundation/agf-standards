# Agent Governance Foundation (AGF)

## Vision

**Agent Governance Foundation (AGF) exists to establish the open trust
and governance standard for autonomous AI agents.**

As AI agents become first-class participants in enterprise systems,
organizations need a consistent way to identify agents, delegate
authority, authorize actions, evaluate risk, revoke permissions, and
produce cryptographically verifiable evidence of every decision.

AGF defines that governance model through open specifications,
interoperable protocols, and a reference implementation that works
across AI frameworks, clouds, and execution environments.

Just as **OAuth** standardized delegated authorization for applications
and **OpenID Connect** standardized identity for users, **AGF aims to
standardize governance for autonomous AI agents.**

------------------------------------------------------------------------

# Mission

Build the universal governance layer that enables organizations to
safely deploy autonomous AI agents by providing:

-   Agent Identity
-   Delegated Authorization
-   Policy Enforcement
-   Trust Evaluation
-   Risk Assessment
-   Revocation
-   Cryptographically Verifiable Decision Evidence
-   Operational Governance

regardless of the protocol, framework, or infrastructure where the agent
operates.

------------------------------------------------------------------------

# What AGF Is

AGF is the governance layer between AI agents and the systems they
interact with.

It determines:

-   Who is acting?
-   Who delegated authority?
-   What policies apply?
-   Should this action be allowed?
-   How trustworthy is this delegation?
-   Can this decision be independently verified later?

Every authorization decision becomes a signed, auditable governance
event.

------------------------------------------------------------------------

# What AGF Is Not

AGF deliberately does **not** replace existing infrastructure.

It is **not**:

-   An Identity Provider (Okta, Microsoft Entra ID, Keycloak)
-   A Secret Manager (HashiCorp Vault)
-   A Key Management System (KMS/HSM)
-   A Certificate Authority (CA)
-   An OAuth Authorization Server
-   An API Gateway

Instead, AGF integrates with these systems while focusing exclusively on
governing autonomous agent behavior.

------------------------------------------------------------------------

# Long-Term Goal

Enable any AI agent---regardless of vendor, framework, or protocol---to
participate in a common governance model where authorization decisions
are portable, verifiable, and trusted across organizational boundaries.

------------------------------------------------------------------------

# The AGF Runtime

The AGF Runtime is the reference implementation of the AGF
specifications.

It delivers:

-   Authorization Engine (PDP)
-   Policy Engine
-   Delegation Engine
-   Trust & Risk Engine
-   Agent Registry
-   Audit & Authorization Decision Records
-   Runtime Monitoring
-   Protocol Adapters (MCP, HTTP, A2A, REST, GraphQL, Browser, CLI)

Organizations can deploy the platform today while remaining aligned with
an open governance standard.

------------------------------------------------------------------------

# Guiding Principle

**Foundation → Specification → Protocol → Runtime → Platform**

-   **Foundation** defines the governance standard.
-   **Specifications** define interoperability.
-   **Protocol** enables trusted communication between agents.
-   **Runtime** is the reference implementation.
-   **Platform** delivers enterprise deployment, operations, and
    governance.
