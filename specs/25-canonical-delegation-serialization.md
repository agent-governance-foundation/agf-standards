# Specification 25: Canonical Delegation Serialization (AGF-C14N-1.0)

**Version:** 0.2.0 (Draft)
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Core format  

## 1. Introduction

Spec 24's Trust Summary needs two things a raw delegation chain doesn't provide on its own: a deterministic byte representation to sign (§4), and a stable hash of "which chain semantically produced this summary" that survives independently of how trust/risk scoring evolves over time (§3). This spec defines both, as a small, dependency-free canonicalization scheme — `AGF-C14N-1.0` — rather than reusing raw JSON serialization, whose key ordering and whitespace are not stable across implementations or even across runs of the same implementation.

## 2. Canonicalization Algorithm

`AGF-C14N-1.0` is a minimal canonical-JSON scheme, RFC-8785-inspired, covering only the value types this protocol's fixed schemas ever use (strings, integers, booleans, arrays, objects — no floating-point numbers anywhere in `AGF-TS-1.0`'s fields or the chain-hash input):

1. Object keys are sorted (recursively, at every nesting level).
2. Separators are compact — `,` and `:`, no insignificant whitespace.
3. UTF-8 encoding.
4. **Floats are rejected**, not coerced — `canonicalize()` raises `TypeError` on any `float` value anywhere in the input (including `NaN`/`Infinity`, which are `float` instances in Python), rather than silently producing output whose numeric formatting isn't portable across implementations. Every field this protocol canonicalizes is an integer, string, boolean, or array/object of those — a float appearing anywhere is a schema violation, not an edge case to handle gracefully.

This is a smaller surface than full RFC 8785 (which also defines ECMAScript-compatible float formatting) precisely because this protocol's schemas never need floats — implementing that part of RFC 8785 would be complexity with no corresponding requirement.

### 2.1 AGF-C14N-1.0 — observable behaviour, stated precisely

The rules above are `AGF-C14N-1.0`. For independent implementations, its output is additionally characterized as follows. This describes behaviour already produced; it adds **no** new constraint, so every object signed or hashed under 1.0 keeps verifying:

- `null` is permitted as a value.
- Object keys are sorted by Unicode code point.
- Strings escape `"` and `\` as `\"` and `\\`; U+0008, U+0009, U+000A, U+000C, U+000D as `\b \t \n \f \r`; every other code point below U+0020 and every non-ASCII code point as `\uXXXX` with lowercase hexadecimal digits, code points above U+FFFF as a UTF-16 surrogate pair. The output is therefore ASCII.
- Integers are written in decimal without a range restriction.

### 2.2 AGF-C14N-1.1

`AGF-C14N-1.1` is `AGF-C14N-1.0` (§2, §2.1) with one added restriction: **integers MUST be within ±(2^53 − 1)**; input outside that range is rejected. For in-range input the output is byte-identical to 1.0. Input with duplicate object keys MUST be rejected when parsed. A format declares which version it uses; Spec 07 §11 signed evidence records use 1.1. Formats already defined on 1.0 (this specification's chain hash and signing input, Spec 26) are unchanged.

## 3. Chain Hash

`chain_hash` (Spec 24's field) is computed by canonicalizing a specific object built from the chain's decoded claims, then taking its SHA-256 digest (hex-encoded):

```json
{
  "hops": [
    {"iss": "...", "sub": "...", "aud": "...", "delegated_scope": [...], "constraints": {...}, "exp": 1234, "hop_index": 0},
    {"iss": "...", "sub": "...", "aud": "...", "delegated_scope": [...], "constraints": {...}, "exp": 1234, "hop_index": 1}
  ],
  "policy_version": "active_<org_id>"
}
```

**Deliberately excluded from the hash input:**
- `delegation_trust_score`, `trust_algorithm`, `trust_algorithm_version` — derived, runtime-computed values. If a trust-scoring algorithm changes, every chain's `chain_hash` must stay exactly the same; only the score attached to it changes. Baking a score into its own stability hash would mean the hash silently changes every time scoring logic is tuned, defeating the point of having a stable reference to "this chain" independent of "how it was scored."
- Raw JWT signatures and headers — the hash is over decoded semantic claims, not wire bytes. Two structurally identical chains re-issued with different (but both valid) signatures produce the same `chain_hash`.
- The enclosing Trust Summary's own `issued_at`/`expires_at` — those describe the summary's own lifetime, not the chain's semantics.

This is verified by construction, not just by convention: `compute_chain_hash()` only ever reads the specific keys listed above from each hop's payload — there is no code path where a trust/risk value could leak into the hash input.

## 4. Signing Input

Spec 24 §4's ES256 signature covers `canonicalize(summary_without_signature_field)` — the full Trust Summary object with the `signature` key itself omitted, canonicalized per §2, signed as raw bytes.

## 5. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
| 0.2.0 | 2026-09-30 | §2.1 states `AGF-C14N-1.0`'s observable behaviour precisely (null, key order, string escaping, integers) without adding constraints; §2.2 adds `AGF-C14N-1.1` (1.0 plus an integer range of ±(2^53 − 1)), used by Spec 07 §11 |
