# Specification 00: AAP-Core — Normative Kernel

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** none  
**Layer:** Kernel  

## 1. Introduction

The Agent Authorization Protocol is specified across 27 documents. That breadth is necessary for a complete governance system, but it is the wrong unit of interoperability: an implementation should not need all 27 specifications to interoperate on accountability.

This specification defines **AAP-Core**, the normative kernel of the protocol: six objects that every conformant implementation MUST support, their minimum required fields, their lifecycle, and the correlation rules that bind them into an auditable record of who acted, under what authority, and with what result. Everything else in the specification suite — trust zones, risk layers, sector controls, transport adapters — is layered above this kernel and MUST NOT redefine it.

The six objects:

| Object | One-line definition |
|--------|--------------------|
| **Actor** | The human, service, or agent instance that acts |
| **Authority** | The scoped, expiring delegation under which it acts |
| **Action** | The exact operation and target |
| **Decision** | Allow, deny, or require human judgment — with policy version |
| **Receipt** | Attempted and actual outcome, correlated to the decision |
| **Invalidation** | Revocation, expiry, supersession, or policy invalidity, as an auditable record |

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY are to be interpreted as described in RFC 2119.

## 2. Layering Model

AAP specifications are organized in four layers:

| Layer | Meaning | Conformance role |
|-------|---------|------------------|
| **Kernel** | This specification: the six objects, their lifecycle, and correlation rules | MUST be implemented in full |
| **Core formats** | The AGF wire serializations of the kernel objects (Specs 01, 02, 05, 06, 07, 08, 09, 10, 25) | MUST be implemented to claim *AGF* conformance; other serializations MAY claim *kernel* conformance only |
| **Profiles** | Domain and policy layers over the kernel: trust zones, risk layers, human oversight, sector controls (Specs 03, 04, 12–18, 24, 26, 27) | OPTIONAL; each profile declares its own conformance target |
| **Adapters** | Transport translation into kernel objects: MCP, A2A, HTTP/REST (Specs 21–23) | OPTIONAL; an adapter MUST translate transport details into kernel objects without redefining them |

An implementation that supports the six kernel objects, satisfies every MUST in this document, and passes the kernel conformance vectors (§6) is **AAP-Core conformant**. Profiles and adapters build on that claim; they never substitute for it.

## 3. The Six Objects

Field tables below define the **abstract kernel model**: minimum semantics every serialization must expose. The AGF wire formats in the referenced specifications are the normative reference serialization; field-name mappings are given per object. Other serializations MAY differ in naming and encoding provided the kernel semantics are preserved and machine-recoverable.

### 3.1 Actor

The entity that acts: a human, a service, or an agent instance.

| Kernel field | Required | Description |
|--------------|----------|-------------|
| `id` | Yes | Globally unique, resolvable identifier |
| `actor_type` | Yes | `human`, `service`, or `agent` |
| `keys` | Conditional | One or more verification methods. REQUIRED for any actor that signs kernel objects (issues Authority, signs Decisions or Receipts); OPTIONAL for actors that act only through an authenticated intermediary |

**AGF serialization:** DIDs and DID documents per Spec 08 (`did:agf:{namespace}:{id}`); `agent_id` in the decision artifact identifies the acting principal (chain leaf subject).

### 3.2 Authority

The scoped, expiring grant under which an Actor acts. Authority is always delegated — it has a grantor — and always expires.

| Kernel field | Required | Description |
|--------------|----------|-------------|
| `id` | Yes | Unique identifier of this grant |
| `grantor` | Yes | Actor `id` of the issuer |
| `grantee` | Yes | Actor `id` of the recipient |
| `scope` | Yes | The permissions granted, as a machine-comparable set |
| `issued_at` | Yes | When the grant was made |
| `expires_at` | Yes | When the grant ceases to be valid. Non-expiring Authority MUST NOT be issued |
| `parent` | No | `id` of the Authority this one was derived from (chain link) |
| `constraints` | No | Additional validity conditions (time, location, etc.) |
| `policy_ref` | No | Policy version to evaluate this Authority under |

**AGF serialization:** the delegation token (Spec 01): `jti`, `iss`, `sub`, `scope`, `iat`, `exp`, `parent`, `constraints`, `policy_version`. Chains of Authority per Spec 02; canonical serialization per Spec 25.

### 3.3 Action

The exact operation attempted, and its target.

| Kernel field | Required | Description |
|--------------|----------|-------------|
| `type` | Yes | The operation, in verb-object form |
| `target` | Yes | The specific resource acted on |
| `context` | No | Request circumstances: timestamp, origin, request correlation id |

**AGF serialization:** `action.type` / `action.resource` / `context` in the decide request (Spec 10 §5.5); scope grammar per Spec 01 §2.5.

### 3.4 Decision

The authorization verdict for one Action under one or more Authorities, evaluated against a specific policy version.

| Kernel field | Required | Description |
|--------------|----------|-------------|
| `id` | Yes | Unique identifier |
| `status` | Yes | Exactly one of `ALLOW`, `DENY`, `REVIEW_REQUIRED` (§4) |
| `qualifiers` | Yes (may be empty) | Advisory markers refining `status` without changing it (§4.2) |
| `action` | Yes | The Action decided on (embedded or by reference) |
| `authority_refs` | Yes | `id`s of every Authority evaluated. Empty only for a `DENY` issued because no Authority was presented |
| `policy` | Yes | The policy version and content hash the decision was evaluated under |
| `decider` | Yes | Actor `id` of the decision point |
| `decided_at` | Yes | Decision time |
| `reasons` | No | Machine-readable reasoning |

**AGF serialization:** the decision artifact `response` + `policy` blocks (Spec 07 §3.1), produced by `POST /v1/decide` (Spec 10 §5.5); policy version identifiers per Spec 06 §4.1.

### 3.5 Receipt

The signed record correlating a Decision to what actually happened. A Decision says what was permitted; a Receipt says what was attempted and what occurred.

| Kernel field | Required | Description |
|--------------|----------|-------------|
| `id` | Yes | Unique identifier |
| `decision_ref` | Yes | `id` of exactly one Decision |
| `attempted` | Yes | Whether execution was attempted after the Decision |
| `outcome` | Yes | `executed`, `not_executed`, or `unknown` |
| `completed_at` | Yes | When the outcome was recorded |
| `signer` | Yes | Actor `id` of the enforcement or observation point |
| `signature` | Yes | Signature over the Receipt content |

Requirements:

- Implementations MUST produce a signed decision artifact for every Decision (Spec 07). The artifact is the Decision's durable record; it is not itself the Receipt.
- An enforcement point that mediates execution (e.g. a protocol gateway, Specs 21–23) SHOULD emit a Receipt recording the actual outcome of the mediated call.
- Where the outcome is not observable by any component of the implementation, `outcome` MUST be `unknown` — it MUST NOT be inferred.
- A Receipt is **evidence, not authority**: presenting a Receipt (or a Decision artifact) MUST NOT authorize any execution (§7.1).

**AGF serialization:** signed audit artifact per Spec 07 §4 (signature rules apply to Receipts identically); query and verification per Spec 07 §6.

### 3.6 Invalidation

An auditable record that something previously valid no longer is. Invalidation unifies four causes that are otherwise easy to scatter across mechanisms:

| Kernel field | Required | Description |
|--------------|----------|-------------|
| `subject` | Yes | `id` of the invalidated thing |
| `subject_type` | Yes | `authority`, `actor_key`, or `policy_version` |
| `cause` | Yes | `revoked`, `expired`, `superseded`, `policy_drift`, or `policy_version_mismatch` |
| `occurred_at` | Yes | When validity ended |
| `detected_at` | Yes | When the implementation recorded it |
| `actor` | Conditional | Actor `id` that caused the invalidation. REQUIRED when `cause` is `revoked` or `superseded` |
| `superseded_by` | No | `id` of the replacing object, when `cause` is `superseded` |
| `evidence` | No | Cause-specific supporting data |

Materialization is tiered by cause:

| Cause | Materialization requirement |
|-------|-----------------------------|
| `revoked`, `superseded` | An Invalidation record MUST be created and queryable — these are explicit acts by an Actor |
| `expired` | MUST be *derivable* from the Authority itself (`expires_at`); a materialized record MAY additionally be created |
| `policy_drift` | MAY produce an Invalidation record when a drift finding changes effective authority (Spec 17) |
| `policy_version_mismatch` | MAY produce an Invalidation record; at minimum the mismatch MUST surface in the Decision (Spec 06 §6.5) |

**AGF serialization:** the revocation entry (Spec 05 §4.3) is the AGF serialization of an Invalidation with `cause` ∈ {`revoked`, `superseded`} — see Spec 05 §4.3.1 for the normative `reason` → `cause` mapping. Expiry derives from Spec 01 §3.2/§3.5. Drift findings per Spec 17.

## 4. Decision States and Qualifiers

### 4.1 The three kernel states

The kernel Decision `status` has exactly three values:

| Status | Meaning |
|--------|---------|
| `ALLOW` | The Action may proceed |
| `DENY` | The Action must not proceed |
| `REVIEW_REQUIRED` | The Action must not proceed until a human judgment is rendered (Spec 15) |

Implementations MUST NOT add states. Anything finer-grained is a qualifier.

### 4.2 Qualifiers

`qualifiers` is a set of advisory markers that refine a status without changing its enforcement semantics: an `ALLOW` with qualifiers is still an allow; a qualifier MUST NOT be required reading to enforce the status correctly.

The kernel defines one qualifier; profiles MAY define others:

| Qualifier | Applies to | Meaning |
|-----------|-----------|---------|
| `caution` | `ALLOW` | Permitted, but under degraded assurance (elevated risk band, stale revocation data, offline fallback) — see Specs 04 §3.2, 05 §5.4, 03 §4.1 |

**AGF serialization note:** the AGF wire formats carry a four-value decision enum in which `ALLOW_WITH_CAUTION` is a distinct value (Specs 04, 10, 21–23). At the kernel level, `ALLOW_WITH_CAUTION` maps to `status: ALLOW` + `qualifiers: ["caution"]`. This is a mapping, not a wire-format change: AGF serializations continue to emit the four-value enum, and adapters translating to kernel form MUST apply this mapping.

## 5. Lifecycle and Correlation Rules

The objects bind into an accountability graph. Conformant implementations MUST maintain the following correlations, and each MUST be machine-traversable from stored records:

1. Every Authority names its `grantor` and `grantee` Actors; every derived Authority names its `parent`.
2. Every Decision names the Action it decided and every Authority it evaluated (`authority_refs`).
3. Every Receipt names exactly one Decision.
4. Every Invalidation names its `subject`; when it replaced something, `superseded_by` names the replacement.
5. Given a stored Decision, an auditor MUST be able to recover: the acting Actor, the full Authority chain evaluated, the exact Action, the policy version and hash applied, and any Receipt or subsequent Invalidation that touches them.

Validity is evaluated at decision time: a Decision is not retroactively falsified by a later Invalidation of an Authority it relied on, but implementations MUST be able to enumerate Decisions affected by a given Invalidation (Spec 05 §5.5 bounds how quickly new Decisions must reflect it).

## 6. Kernel Conformance Vectors

Positive-path conformance is covered by the categories in Spec 11. The kernel additionally REQUIRES the following negative vectors — an implementation MUST produce the expected outcome for each. Vector artifacts ship in the `schemas/` fixtures and the conformance suite.

| ID | Vector | Expected outcome |
|----|--------|------------------|
| KERNEL-NEG-01 | Expired delegation: Authority presented after `expires_at` | `DENY`; expiry derivable per §3.6; error `EXPIRED` |
| KERNEL-NEG-02 | Replayed action: a previously evaluated request (same Authority, Action, and request correlation id) re-presented, or a Decision/Receipt artifact presented as authorization | Fresh evaluation or rejection — a stored `ALLOW` MUST NOT be honored as bearer authority (§7.1); duplicate `jti` issuance MUST be rejected (Spec 01 §5.3) |
| KERNEL-NEG-03 | Policy-version mismatch: requested `policy_ref` unavailable to the decider | MUST NOT evaluate under a different policy version; the mismatch MUST surface in the Decision per Spec 06 §6.5. Reconciliation of Spec 11 POLICY-09/10 with this rule is tracked in RFC 0001 |
| KERNEL-NEG-04 | Revoked parent grant: Invalidation (`cause: revoked`) exists for an ancestor of the presented Authority | `DENY` for the entire branch (Spec 05 §3); error `REVOKED` |
| KERNEL-NEG-05 | Receipt for a denied action: a Receipt with `outcome: executed` whose `decision_ref` is a `DENY` or unresolved `REVIEW_REQUIRED` | The Receipt MUST verify as signature-valid but MUST be reported as an enforcement violation by audit verification (Spec 07 §6.3) |

## 7. Security Considerations

### 7.1 Receipts are evidence, not authority

Decision artifacts and Receipts are signed evidence about the past. Accepting either as authorization for a new execution converts an audit trail into a bearer-token system with no expiry. KERNEL-NEG-02 exists to make this failure mode a conformance failure, not just a design note.

### 7.2 Invalidation timeliness

A kernel-conformant implementation is only as accountable as its Invalidation propagation. The kernel deliberately does not set propagation bounds — Spec 05 §5.5 does — but implementations MUST NOT report an Invalidation as recorded (`detected_at`) before it is queryable by the components that enforce it.

### 7.3 The `unknown` outcome

Receipt `outcome: unknown` is honest but weak: a system in which most Receipts are `unknown` proves decisions were made, not that they were enforced. Deployments SHOULD place enforcement points (adapters, Specs 21–23) where outcomes are observable, and auditors SHOULD treat the `unknown` rate as a monitored metric.

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-14 | Initial kernel specification, extracted as the normative core of Specs 01–27 (RFC 0001) |
