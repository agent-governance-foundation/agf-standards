# RFC 0001: AAP-Core — a normative kernel for the Agent Authorization Protocol

- **Author(s):** AGF maintainers
- **Affected spec(s):** New specification (Spec 00); editorial changes to Specs 05, 11 and the specification index
- **Status:** Draft
- **Discussion:** https://github.com/aaif/project-proposals/issues/38

## Summary

Factor the six objects every AAP implementation already depends on — Actor, Authority, Action, Decision, Receipt, Invalidation — into a small normative kernel (Spec 00, "AAP-Core"), and reclassify the existing 27 specifications as Core formats, Profiles, and Adapters layered above it. No wire format changes; the kernel is a conformance spine, not a new protocol.

## Background

This RFC is a direct response to feedback received on AAIF project proposal #38
(https://github.com/aaif/project-proposals/issues/38) and the subsequent
discussion with hegu-1 regarding the Enterprise AI OS Architecture governance
templates (https://github.com/hegu-1/enterprise-ai-os-architecture/tree/main/layers/07-governance).

The feedback identified that a 27-spec standard is too large for interoperability,
and that a small normative kernel (Actor, Authority, Action, Decision, Receipt,
Invalidation) would be more appropriate for broad adoption.

## Motivation

Today, "implementing AAP" has no smaller unit than the full specification suite. That is the wrong shape for three audiences:

- **Independent implementers** need a bounded target: what is the minimum they must build to interoperate on accountability? Today the honest answer is "read all 27 and decide."
- **Standards bodies** need a small normative core they can anchor conformance and IP policy to, with domain material layered as optional profiles.
- **Transport adapters** (MCP, A2A, HTTP/REST — Specs 21–23) already translate transport details into a common set of decision and audit objects. That common set exists in practice but is not named normatively anywhere.

All six kernel objects already exist in the AGF wire formats (delegation tokens and chains, the decide API, the decision artifact, revocation entries). The work is extraction and naming, not invention.

## Proposed change

1. **New Spec 00 — AAP-Core.** Defines the six kernel objects with minimum required fields, lifecycle and correlation rules, the three-state Decision model, and kernel conformance vectors. Existing specs are the normative reference serialization; other serializations may claim kernel conformance if they preserve the semantics.

2. **Decision states.** The kernel Decision `status` is exactly `ALLOW` / `DENY` / `REVIEW_REQUIRED`, plus an extensible `qualifiers` set. The AGF wire enum's `ALLOW_WITH_CAUTION` maps to `ALLOW` + `qualifiers: ["caution"]`. Wire formats are unchanged; the mapping is normative for adapters translating to kernel form.

3. **Invalidation as a first-class object.** One record shape covering `revoked`, `expired`, `superseded`, `policy_drift`, and `policy_version_mismatch`, with tiered materialization: explicit acts (revocation, supersession) MUST be materialized and queryable; expiry MUST be derivable from the Authority itself; drift and version mismatch MAY materialize. Spec 05 gains a normative mapping from its revocation `reason` values to the kernel `cause` enum.

   One deliberate design decision: Spec 05's `policy_change` reason maps to kernel cause `revoked`, **not** `policy_drift`. The kernel `cause` enum describes the *mechanism* by which validity ended; a policy-motivated revocation is still an explicit revocation act by an authority, with the motive preserved in the serialization's `reason` field. `policy_drift` is reserved for invalidation produced by behavioral drift findings (Spec 17), which is future work (see below).

4. **Negative conformance vectors.** Five kernel-required vectors: expired delegation, replayed action, policy-version mismatch, revoked parent grant, and a valid receipt for a denied action. These extend Spec 11's test categories and will ship as fixtures under `schemas/` and `conformance/`.

5. **Index reclassification.** The specification index groups the 27 specs as Kernel / Core formats / Profiles / Adapters (plus operational documents). Editorial only; no spec renumbering.

6. **Machine-readable schemas.** JSON Schemas (draft 2020-12) for the six kernel objects, each with valid and invalid example fixtures, seeding the `schemas/` directory.

## Backward compatibility

No breaking changes. All existing wire formats, already-issued tokens, chains, and audit artifacts remain valid; the four-value decision enum stays on the wire. Implementations conformant to the existing specs are AAP-Core conformant for the REQUIRED tier by construction. The two SHOULD-tier behaviors (execution receipts at enforcement points; drift-linked invalidation) are new but optional at this maturity level.

## Security considerations

The kernel makes two existing implicit properties explicit and testable:

- **Receipts are evidence, not authority.** Accepting a stored decision or receipt as authorization for a new execution turns the audit trail into an unexpiring bearer-token system. The replayed-action vector makes this a conformance failure.
- **Enforcement-violation detection.** The receipt-for-denied-action vector requires audit verification to flag a signature-valid receipt that contradicts its decision, closing the gap between "decisions were recorded" and "decisions were enforced."

No new attack surface is introduced; the kernel adds no endpoints or formats beyond a schema for records that already exist.

## Alternatives considered

- **Do nothing.** Keeps the 27-spec suite as the only conformance unit; every adopter re-derives the core themselves, inconsistently. This is the status quo the AAIF feedback identified as a barrier.
- **Adopt an external kernel schema set directly.** The referenced governance templates are useful prior art, but AAP's objects carry protocol-specific semantics (chain correlation, decision-time validity, propagation bounds) that must stay aligned with Specs 01–07; the kernel must be extracted from, not bolted onto, the existing normative text.
- **Publish the kernel as a separate repository/standard.** Maximizes reuse but splits governance of tightly coupled normative text. Layering within one suite achieves the same adoption shape with one change process.

## Unresolved questions

- Whether Specs 24–27 (cross-organization trust) should be grouped as a named "Federation" profile in the index.
- Community review: the removal of POLICY-09's trusted-issuer fallback (see Resolved during draft) remains explicitly open for community input during this RFC's discussion period.

## Resolved during draft

- **Spec 06 §6.5 vs Spec 11 POLICY-09/10** (2026-07-14): the two specs disagreed on policy-version-not-found behavior — Spec 06 required a uniform `NOT_APPLICABLE` with no fallback (which the reference implementation follows), while POLICY-09 described an issuer-trust-gated fallback. Resolved in Spec 06's favor: the trusted-issuer fallback is removed; a missing requested version MUST surface in the decide response (`error_code: POLICY_VERSION_NOT_FOUND`, `policy_version_requested` / `policy_version_applied: null`) and the decision is capped at `ALLOW_WITH_CAUTION`, mirroring the stale-revocation-list precedent (Spec 05 §5.4). See Spec 06 0.2.0, Spec 10 0.3.0, Spec 11 0.3.0, and the concretized KERNEL-NEG-03 in Spec 00 0.1.1.
- Whether Receipt `outcome` observation and drift-linked Invalidation move from SHOULD to MUST when Spec 00 advances past Working Draft.
- **Execution receipts** (2026-07-15): the gateways now emit signed Execution Receipts for every mediated decision (Spec 07 §10), and `/v1/audit/verify` is two-stage with structured violation codes (Spec 07 §6.3.1) — KERNEL-NEG-05 is fully testable.
- **Drift correlation** (2026-07-15): automated responses to critical drift findings create revocations with reason `behavioral_drift` and the finding as `evidence` (Spec 05 §4.3.1, Spec 17), realizing the kernel `policy_drift` cause.
