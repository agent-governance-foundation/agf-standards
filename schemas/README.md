# Schemas

Machine-readable definitions of the wire formats specified in [specs/](../specs/). Prose specs are for humans; these are for validators, code generators, and CI.

## Planned artifacts

| Artifact | Source spec | Status |
|---|---|---|
| `delegation-token.schema.json` | Spec 01 — Delegation Token Format | planned |
| `delegation-chain.schema.json` | Spec 02 — Delegation Chain | planned |
| `audit-record.schema.json` | Spec 07 — Audit Trail | planned |
| `did-document.schema.json` | Spec 08 — Identity Registry | planned |
| `trust-summary.schema.json` | Spec 24 — Trust Summary Format | planned |
| `decision-api.openapi.yaml` | Spec 10 — API Protocol | planned |

## Rules

- The prose spec is normative. If a schema and its spec disagree, the spec wins and the schema has a bug — file an issue.
- Schemas use JSON Schema draft 2020-12; APIs use OpenAPI 3.1.
- Every schema ships with valid and invalid example documents used by the [conformance suite](../conformance/).

Extraction from the prose specs is in progress — contributions welcome, see [CONTRIBUTING.md](../CONTRIBUTING.md).
