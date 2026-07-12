# Governance

This document describes how the AGF specifications are maintained and how decisions about them are made.

## Current phase: incubation

The AGF standards are in their initial public phase. They are maintained by the Agent Governance Foundation maintainer team, which currently holds final decision authority. Our stated intent is to move to neutral, multi-stakeholder governance (a technical steering committee with seats earned through contribution and implementation) as independent implementations and contributors arrive. Openness of process precedes openness of control — but both are the goal.

## Roles

- **Maintainers** — merge rights and final say on spec content. Listed in [MAINTAINERS.md](MAINTAINERS.md).
- **Contributors** — anyone who files an issue, opens a PR, or submits an RFC.
- **Implementers** — anyone building against the specifications. Implementation experience reports carry particular weight in promoting a spec's maturity.

## How decisions are made

1. **Editorial changes** (typos, wording, formatting, non-normative clarifications) — direct pull request; any maintainer may merge under lazy consensus.
2. **Substantive changes** (anything that alters a MUST/SHOULD/MAY, a wire format, an algorithm, or interoperability behavior) — require an [RFC](rfcs/README.md). RFCs get a public discussion period, then a maintainer decision recorded on the PR. A substantive change to a **Stable** spec additionally requires evidence that existing conformant implementations have a migration path.
3. **New specifications** — start life as an RFC proposing the spec's scope, then enter `specs/` as a Working Draft.

## Specification lifecycle

`Working Draft → Candidate → Stable → Deprecated`

Promotion criteria:

- **Working Draft → Candidate**: spec is feature-complete; normative statements use RFC 2119 language; machine-readable schemas for its wire formats exist in [schemas/](schemas/); open issues against it are triaged.
- **Candidate → Stable**: at least two independent implementations demonstrate interoperability by passing the spec's [conformance](conformance/) tests; no unresolved normative ambiguities.
- **Deprecation**: by RFC only, and the deprecating RFC must name the successor.

## Versioning

Each specification is versioned independently using semantic versioning:

- **Patch** (0.1.0 → 0.1.1): editorial only, no normative change.
- **Minor** (0.1.x → 0.2.0): backward-compatible normative additions.
- **Major** (0.x → 1.0, 1.x → 2.0): breaking changes to wire formats or required behavior. Not permitted for Stable specs without an RFC that includes a migration path.

Every spec carries its own changelog table recording version, date, and changes.

## Amendments to this document

Changes to this governance document follow the RFC process.
