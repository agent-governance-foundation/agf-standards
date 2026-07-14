# Conformance

How an independent implementation proves it complies with the AGF specifications.

[Spec 11 — Conformance](../specs/11-conformance.md) defines the conformance model: test categories, conformance levels, and the test-case format. This directory will hold the runnable artifacts:

- **Test vectors** — signed tokens, chains, and audit records (valid and deliberately invalid) with expected verification outcomes. An implementation runs its own verifier against them and compares results.
- **Conformance suite** — a runnable harness that drives an implementation's API per Spec 10 and checks behavior against the specs.
- **Self-certification checklist** — a per-spec checklist an implementer completes and publishes alongside their conformance claim.

## Status

The full suite is not yet published; Spec 11 describes the target. Until the suite exists, no implementation — including our own reference implementation — can formally claim AGF conformance levels, and "AGF Conformant" claims should not be made.

**First published artifacts:** the AAP-Core kernel schemas and fixtures in [schemas/kernel/](../schemas/kernel/) — six JSON Schemas for the kernel objects (Spec 00 §3) with valid/invalid example documents and a runnable checker (`python3 schemas/kernel/check.py`, exercised in CI). The kernel negative vectors (Spec 00 §6, Spec 11 §3.11) are defined normatively; the schema-checkable ones ship as fixtures there, and the behavioral ones (expired delegation, revoked parent grant) will land with the runnable harness.

## Trademark note

Implementing the specifications is free and requires no permission (see [LICENSE](../LICENSE)). Using AGF conformance marks in marketing is contingent on passing the published suite once it exists — this is how the ecosystem keeps "conformant" meaningful.
