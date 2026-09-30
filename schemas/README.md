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

## Core-format schemas (available)

Non-kernel AGF artifacts that correlate to the kernel objects without extending
them (Spec 00 §2's Core-format layer):

| Schema | Source spec |
|---|---|
| [`execution-validation-record.schema.json`](execution-validation-record.schema.json) | Spec 30 §4 — Execution Validation Record (unsigned form) |
| [`approval-request-record.schema.json`](approval-request-record.schema.json) | Spec 07 §11.3 — signed Approval Request Record |
| [`approval-attestation-record.schema.json`](approval-attestation-record.schema.json) | Spec 07 §11.4 — signed Approval Attestation |
| [`invalidation-record.schema.json`](invalidation-record.schema.json) | Spec 07 §11.5 — signed Invalidation Record |
| [`execution-validation-signed-record.schema.json`](execution-validation-signed-record.schema.json) | Spec 07 §11.6 — signed Execution Validation Record |

Each schema has a `fixtures/<name>.valid.json` and one or more
`fixtures/<name>.invalid[.<reason>].json`, where `<reason>` names the one rule the
fixture breaks. `check.py` validates them all:

```
pip install jsonschema
python3 schemas/check.py
```

The signed-evidence schemas check **structure** only. The event-time invariant,
bindings between records, ordering and every other rule in Spec 07 §11.8 are
semantic rules that a verifier applies; a schema-valid record is not thereby
verified. The `signature` values in the fixtures are placeholders, not valid
signatures.

`fixtures/signed-evidence.revocation-cases.json` lists revocation-classification
cases for Spec 07 §11.8 (revoked before the decision, delayed detection, revoked after
the decision, no record) with their expected status and code; `check.py` evaluates
each against a reference classifier.

`check.py` exits non-zero if `jsonschema` is not installed or a required data file is
missing: a check that could not run is reported as a failure, never as a pass.

`fixtures/signed-evidence.vectors.json` carries test vectors for `AGF-C14N-1.1`
canonicalization (Spec 25 §2.2) and salted digests (Spec 07 §11.2), including
non-ASCII and astral characters. `check.py` re-derives every vector from its input,
so a wrong vector fails the check. The vector salt is fixed for reproducibility;
real salts MUST be fresh and random.

`execution-validation-record.invalid.json` fails because `result: "invalid"`
is reported with no `reasons` — an invalid result with no stated cause defeats
the audit purpose of the record (Spec 30 §4).

## Planned artifacts

The remaining AGF wire formats — the reference serialization of the kernel
objects — are tracked separately, not yet built:

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
