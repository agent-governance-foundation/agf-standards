# Kernel fixtures

Example documents for the six kernel schemas in [`../`](../), used by [`check.py`](../check.py).

## Convention

- `<object>.valid.json` — a document that satisfies `<object>.schema.json`.
- `<object>.invalid.json` — a document that fails `<object>.schema.json` for a
  kernel-meaningful reason (not just a typo).
- `kernel-neg-05.decision.json` / `kernel-neg-05.flagged.json` — a special pair,
  see below.
- `authority-jwt.valid.json` / `authority-jwt.invalid.json` — a special pair,
  see below.

## authority-jwt: JWT-to-kernel mapping conformance

`authority.schema.json` models the abstract kernel Authority object
(`id`/`grantor`/`grantee`/...), not any one wire format — Spec 00 §3.2 gives
the normative mapping to AGF's actual JWT delegation-token claims
(`jti`→`id`, `iss`→`grantor`, `sub`→`grantee`, `iat`→`issued_at`,
`exp`→`expires_at`, `parent`→`parent`, `constraints`→`constraints`,
`policy_version`→`policy_ref`). Nothing else in this repo checks that the
mapping is actually applied correctly — a document can satisfy
`authority.schema.json` in isolation while still misattributing which party
is the grantor and which is the grantee.

These two fixtures are each `{"jwt_claims": {...}, "kernel_mapped": {...}}`
— `check.py` applies the Spec 00 §3.2 mapping to `jwt_claims` and asserts
the result equals `kernel_mapped` (mapping fidelity) **and** that
`kernel_mapped` validates against `authority.schema.json` (structural
conformance). Both must hold for `.valid.`; at least one must fail for
`.invalid.`. `authority-jwt.invalid.json`'s `kernel_mapped` is individually
schema-valid (all required fields present, correct types) but swaps
`grantor`/`grantee` relative to what `jwt_claims`'s `iss`/`sub` actually
say — proving this check catches mapping errors that pure schema validation
would miss entirely.

All example data is fictional (`example.com`, `acme` namespace); no production
identifiers appear in this repository.

## Invalid fixtures and why they fail

| Fixture | Fails because |
|---|---|
| `actor.invalid.json` | `actor_type: "bot"` is not one of `human`, `service`, `agent` |
| `authority.invalid.json` | `expires_at` is missing — kernel Authority always expires (§3.2) |
| `action.invalid.json` | `target` is missing — an Action without a target is not an Action |
| `decision.invalid.json` | `status: "ALLOW_WITH_CAUTION"` — a wire-format enum value leaking into kernel form; the kernel has exactly three states, and `caution` is a qualifier, not a status (§4) |
| `receipt.invalid.json` | `outcome: "success"` is not one of `executed`, `not_executed`, `unknown` |
| `invalidation.invalid.json` | `cause: "revoked"` with no `actor` — `actor` is REQUIRED when `cause` is `revoked` or `superseded` (§3.6) |

## KERNEL-NEG-05: a semantic, cross-object vector

`kernel-neg-05.flagged.json` is a Receipt with `outcome: "executed"`.
`kernel-neg-05.decision.json` is its correlated Decision, with `status: "DENY"`
(`kernel-neg-05.flagged.json`'s `decision_ref` matches `kernel-neg-05.decision.json`'s `id`).

Both documents are individually schema-valid — `check.py` validates each of
them as **valid**. Neither schema, on its own, can see that a Receipt claims
execution against a Decision that forbade it. Detecting KERNEL-NEG-05 (Spec 00
§6) requires reading both objects together and applying the audit
verification rule in Spec 07 §6.3: a Receipt reporting `executed` against a
`DENY` (or an unresolved `REVIEW_REQUIRED`) MUST be flagged as an enforcement
violation. That check is semantic, not structural, so it is out of scope for
JSON Schema and is exercised by the conformance suite instead.

## Mapping to Spec 00 §6 kernel conformance vectors

Spec 00 §6 defines five negative vectors. Only some of what they test is
schema-checkable; the rest is behavioral (requires evaluating a request at a
point in time, walking a chain, or comparing two records) and is exercised by
the conformance suite, not by these fixtures.

| Vector | Schema-checkable part covered here | Behavioral part (conformance suite only) |
|---|---|---|
| KERNEL-NEG-01 — expired delegation | `authority.invalid.json` shows `expires_at` is a required field | Whether a *specific* Authority is expired depends on comparing `expires_at` to the current time — not visible to a schema |
| KERNEL-NEG-02 — replayed action | — | Entirely behavioral: requires request/decision history and duplicate-`jti` tracking |
| KERNEL-NEG-03 — policy-version mismatch | — | Entirely behavioral: requires knowing which policy versions the decider has available |
| KERNEL-NEG-04 — revoked parent grant | `invalidation.invalid.json` shows `actor` is required when `cause: "revoked"`, the field that makes revocation records attributable and queryable | Whether a *specific* Authority chain has a revoked ancestor requires walking the chain — not visible to a schema |
| KERNEL-NEG-05 — receipt for a denied action | `kernel-neg-05.flagged.json` + `kernel-neg-05.decision.json` (see above) | The cross-object flagging rule itself (Spec 07 §6.3) is applied by audit verification, not schema validation |

## Running the check

From the repo root:

```
python3 schemas/kernel/check.py
```

Or from this directory's parent (`schemas/kernel/`):

```
python3 check.py
```

If `jsonschema` is installed, every fixture is validated against its schema
and the script fails if any `*.valid.json` or `kernel-neg-05*` fixture fails
validation, or any `*.invalid.json` fixture passes validation. If
`jsonschema` is not installed, the script falls back to a JSON
well-formedness check and prints a note — it cannot confirm schema
conformance in that mode.
