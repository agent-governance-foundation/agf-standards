# Schemas

Machine-readable definitions of the wire formats specified in [specs/](../specs/). Prose specs are for humans; these are for validators, code generators, and CI.

## Kernel schemas (available)

The six normative kernel objects from Spec 00 — AAP-Core — are specified as
JSON Schema (draft 2020-12) under [`kernel/`](kernel/):

| Schema | Source spec |
|---|---|
| `kernel/actor.schema.json` | Spec 00 — AAP-Core |
| `kernel/authority.schema.json` | Spec 00 — AAP-Core |
| `kernel/action.schema.json` | Spec 00 — AAP-Core |
| `kernel/decision.schema.json` | Spec 00 — AAP-Core |
| `kernel/receipt.schema.json` | Spec 00 — AAP-Core |
| `kernel/invalidation.schema.json` | Spec 00 — AAP-Core |

These model the *abstract kernel* fields from Spec 00 §3 — the minimum every
serialization must expose — not any one wire format. `kernel/fixtures/`
carries paired valid/invalid example documents per object plus a
cross-object semantic vector (KERNEL-NEG-05); see
[`kernel/fixtures/README.md`](kernel/fixtures/README.md) for the mapping to
Spec 00 §6's conformance vectors. `kernel/check.py` validates every fixture
against its schema (falls back to a JSON well-formedness check if
`jsonschema` isn't installed).

## Planned artifacts

The AGF wire formats — the reference serialization of the kernel objects —
are tracked separately:

| Artifact | Source spec | Status |
|---|---|---|
| `delegation-token.schema.json` | Spec 01 — Delegation Token Format | planned |
| `delegation-chain.schema.json` | Spec 02 — Delegation Chain | planned |
| `audit-record.schema.json` | Spec 07 — Audit Trail | planned |
| `execution-receipt.schema.json` | Spec 07 §10 — Execution Receipts | planned |
| `did-document.schema.json` | Spec 08 — Identity Registry | planned |
| `trust-summary.schema.json` | Spec 24 — Trust Summary Format | planned |
| `decision-api.openapi.yaml` | Spec 10 — API Protocol | planned |

## Rules

- The prose spec is normative. If a schema and its spec disagree, the spec wins and the schema has a bug — file an issue.
- Schemas use JSON Schema draft 2020-12; APIs use OpenAPI 3.1.
- Every schema ships with valid and invalid example documents used by the [conformance suite](../conformance/).

Extraction from the prose specs is in progress — contributions welcome, see [CONTRIBUTING.md](../CONTRIBUTING.md).
