# Conformance

How an independent implementation proves it complies with the AGF specifications.

[Spec 11 — Conformance](../specs/11-conformance.md) defines the conformance model: test categories, conformance levels, and the test-case format. This directory will hold the runnable artifacts:

- **Test vectors** — signed tokens, chains, and audit records (valid and deliberately invalid) with expected verification outcomes. An implementation runs its own verifier against them and compares results.
- **Conformance suite** — a runnable harness that drives an implementation's API per Spec 10 and checks behavior against the specs.
- **Self-certification checklist** — a per-spec checklist an implementer completes and publishes alongside their conformance claim.

## Status

The suite is not yet published; Spec 11 describes the target. Until the suite exists, no implementation — including our own reference implementation — can formally claim AGF conformance levels, and "AGF Conformant" claims should not be made.

## Trademark note

Implementing the specifications is free and requires no permission (see [LICENSE](../LICENSE)). Using AGF conformance marks in marketing is contingent on passing the published suite once it exists — this is how the ecosystem keeps "conformant" meaningful.
