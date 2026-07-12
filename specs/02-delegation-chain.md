# Specification 02: Delegation Chain Semantics

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.7

## 1. Introduction

Multiple delegation tokens can form a chain, where each token's subject delegates authority to the next token's issuer. This specification defines how chains are formed, validated, and traversed, including operational limits for production deployment.

## 2. Chain Definition

### 2.1 Chain Structure

A delegation chain is an ordered list of tokens where for each consecutive pair `(token[i], token[i+1])`:

```
token[i].sub == token[i+1].iss
```

The first token's issuer is the **root authority** (typically a human or system administrator). The last token's subject is the **leaf agent** requesting an action.

### 2.2 Chain Representation

```json
{
  "chain": ["jwt_1", "jwt_2", "jwt_3"],
  "action": {
    "type": "read:calendar",
    "resource": "calendars/alice@acme.com"
  },
  "context": {
    "timestamp": 1735603300,
    "source_ip": "10.0.1.45"
  }
}
```

### 2.3 Chain Diagram

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│  Alice  │───▶│ Agent A │───▶│ Agent B │───▶│ Agent C │
└─────────┘    └─────────┘    └─────────┘    └─────────┘
   iss           sub/iss         sub/iss         sub
                 token 1         token 2         token 3
```

### 2.4 Acting Agent / Principal Identity

The **acting principal** for a request — the identity used for reputation lookups, audit attribution, HITL routing, and discovery gating — MUST be derived from the **last token in the chain**, not the first:

```
acting_principal = chain[-1].sub
immediate_delegator = chain[-1].iss
```

`chain[0].iss` is the **root authority** (§2.1) — typically a human or system administrator — and MUST NOT be used as the acting principal for chains of length > 1. A single-hop chain (`chain[0].iss` is also the immediate delegator) is the only case where root authority and immediate delegator coincide.

This is a normative rule, not an implementation detail: any subsystem that reads chain identity (reputation scoring, audit logging, HITL escalation, discovery) MUST apply it consistently. Divergent implementations of this rule across subsystems silently misattribute every action in a chain deeper than one hop to the root grantor instead of the real actor.

## 3. Chain Validity Rules

### 3.1 Continuity

Each consecutive pair MUST satisfy `token[i].sub == token[i+1].iss`. Violation results in `CHAIN_BROKEN` error.

### 3.2 Expiration

Every token in the chain MUST have `exp > current_time`. A single expired token invalidates the entire chain.

### 3.3 Revocation

If any token's `jti` appears in a revocation list, the entire chain is invalid (branch cut semantics — see Spec 05).

**Implementation note:** revocation is checked as a separate pass over the chain, after structural validation (§3.1, §3.2, §3.4-§3.6) has succeeded — not as one more per-token check folded into the main validation loop. It runs against an injected revocation port so the storage backend (file, Postgres) is swappable without touching chain-validation logic. Two call shapes exist depending on backend capability: a synchronous per-token lookup, and an async batch lookup (fetch all revoked IDs once, then check each token's `jti` against the set) for backends that support it. Both enforce the same rule; the batch form exists purely for efficiency on chains with many hops.

### 3.4 Signature

Every token's signature MUST be valid against its issuer's public key.

### 3.5 Scope Inheritance

The effective scope of the chain is the intersection of all tokens' scopes. All scopes MUST be canonicalized (see Spec 01 §2.7) before comparison:

```
effective_scope = canonicalize(token[0].scope) ∩ canonicalize(token[1].scope) ∩ ... ∩ canonicalize(token[n].scope)
```

The requested action's scope MUST be a subset of the effective scope.

**Scope is strictly narrowing:**

Delegation can only restrict scope — it can never expand it. An agent cannot grant more permissions than it received, regardless of its trust score or position in the organization. The intersection operation enforces this: each additional hop in the chain can only reduce (or hold equal) the set of allowed actions; it can never add new ones.

This is an intentional architectural constraint, not a limitation. It means: if an agent needs broader scope than its current delegation provides, a new delegation must be issued from an ancestor that holds the required authority. Higher trust scores (Spec 04) influence *risk weighting* on decisions but cannot substitute for missing scope entries in the chain.

### 3.6 Depth Limits

If any token contains a `max_depth` claim, the chain length (number of tokens) MUST NOT exceed `min(max_depth_i) + 1` (the first token counts as depth 0). When no token in the chain claims `max_depth`, the implicit ceiling is the default depth limit below, aligned with Spec 03 §4.2's Domain zone requirement (full-chain tracking up to depth 10).

**Operational depth limits:**

| Limit Type | Value | Behavior if Exceeded |
|------------|-------|----------------------|
| Default (no explicit `max_depth` claim) | 10 | `DEPTH_EXCEEDED` — same rejection as an explicit claim being exceeded |
| Soft limit | 10 | `SOFT_DEPTH_EXCEEDED` warning on the validation result (logged + recorded in decision reasoning); extra trust deduction of 5 points per token beyond the limit |
| Hard limit | 20 | Chain rejected with `MAX_DEPTH_EXCEEDED` |

### 3.7 Constraints Validation

If any token contains a `constraints` object, the verifier MUST evaluate all constraints against the request context.

**Supported constraint types:**

| Constraint | Format | Evaluation |
|------------|--------|------------|
| `time_of_day` | array of `"HH:MM-HH:MM"` | Current time must fall within at least one range |
| `location` | array of strings | Current location (from context) must match at least one value |
| `ip_range` | array of CIDRs | Source IP must fall within at least one range |

**Example:**

```json
"constraints": {
  "time_of_day": ["09:00-17:00"],
  "location": ["office", "vpn"],
  "ip_range": ["10.0.0.0/8"]
}
```

Constraints are evaluated **after** signature validation and **after** trust score calculation (including reputation adjustment). If any constraint fails, the verifier MUST reject the chain with error `CONSTRAINT_VIOLATION`.

**Note on ordering:** an earlier version of this spec required constraints to be evaluated before trust score. The current implementation computes structural trust score during chain validation, applies a reputation-based adjustment, and only then evaluates constraints. Since a constraint violation is a hard rejection regardless of trust score, this ordering does not change the final decision — only the sequence in which intermediate values are computed and logged. Reordering to match the original before-trust-score sequencing is a possible future cleanup, not a correctness fix.

### 3.8 Performance Budget

Chain validation has a performance budget:

| Metric | Target | Maximum |
|--------|--------|---------|
| Validation time (depth=3) | < 10ms | 30ms |
| Validation time (depth=10) | < 30ms | 80ms |
| Per-token overhead | < 2ms | 5ms |

If validation exceeds the maximum, the implementation MUST log a performance alert and MAY reject the chain with `PERFORMANCE_BUDGET_EXCEEDED`.

An implementation may express the table above as a single per-chain budget of `max(30ms, 8ms × chain length)` — consistent with the two anchor rows above — and take the alert-plus-metric path (a log line plus a counter and latency histogram) without rejecting: budget breaches indicate node health, not request validity.

## 4. Scope Inheritance Examples

### Example 1: Narrowing

```
Token 1 scope: [read:calendar, write:calendar, read:contacts]
Token 2 scope: [read:calendar]
Token 3 scope: [read:calendar, read:contacts]

Effective scope: [read:calendar]  # Intersection of all three
```

### Example 2: Empty Intersection

```
Token 1 scope: [read:calendar]
Token 2 scope: [write:calendar]

Effective scope: []  # Empty — no permissions
```

## 5. Delegation Tree vs Chain

While a single request follows a chain from root to leaf, the underlying authorization structure forms a tree:

```
                Alice
               /     \
        Agent A       Agent B
        /    \             \
   Agent C   Agent D     Agent E
```

When Agent C requests an action, the chain is `[Alice → Agent A → Agent C]`. The other branches are irrelevant to this request.

## 6. Chain Validation Algorithm

The current implementation splits this across two layers: a pure `validate_chain()` (structural checks — signature, expiration, continuity, depth, scope, trust score) and an orchestrating decision service that calls it, then separately checks revocation and evaluates constraints. This split exists so structural validation stays a pure domain function testable without a revocation store or constraint context.

```python
# Layer 1: structural validation (pure — no I/O beyond key resolution)
def validate_chain(chain, action, audience, key_resolver, current_time):
    effective_scope = None

    if len(chain) > HARD_DEPTH_LIMIT:
        return error("MAX_DEPTH_EXCEEDED")

    for i, token in enumerate(chain):
        # 1. Verify signature, expiration, audience, required claims (incl. 90-day
        #    lifetime cap — Spec 01 §3.5), future-dated iat — one shared per-token check
        result = verify_single_token(token, audience, key_resolver, now=current_time)
        if not result.ok:
            return error(result.error.code, i)
        payload = result.payload

        # 2. Check depth limit (defaults to 10 if the token omits max_depth —
        #    reconciled with Spec 03 §4.2's Domain zone requirement)
        max_depth = payload.get("max_depth", DEFAULT_MAX_DEPTH)
        if len(chain) - 1 > max_depth:
            return error("DEPTH_EXCEEDED", i)

        # 3. Update effective scope (with canonicalization)
        token_scope = set(canonicalize(s) for s in payload.scope)
        effective_scope = token_scope if effective_scope is None else effective_scope & token_scope

    # 4. Check continuity across the whole chain
    if not continuous(chain):
        return error("CHAIN_BROKEN")

    # 5. Check action against effective scope
    if canonicalize(action.scope) not in effective_scope:
        return error("SCOPE_INSUFFICIENT")

    return success(trust_score=calculate_trust_score(chain, current_time), effective_scope=effective_scope)


# Layer 2: orchestration (decide_service) — revocation, reputation, constraints
def decide(request, current_time):
    chain_result = validate_chain(request.chain, request.action, request.audience, key_resolver, current_time)
    if not chain_result.valid:
        return deny(chain_result.error)

    # 6. Check revocation (separate injected port — see §3.3)
    if any_token_revoked(request.chain, revocation_port, current_time):
        return deny("REVOKED")

    # 7. Adjust trust score with behavioral reputation (Spec 04)
    adjusted_trust_score = max(0, chain_result.trust_score + reputation_penalty(acting_principal))

    # 8. Evaluate constraints (after trust score — see §3.7 ordering note)
    if not evaluate_constraints(request.chain, request.context).passed:
        return deny("CONSTRAINT_VIOLATION")

    return decide_with_risk(adjusted_trust_score, ...)
```

## 7. Example: Valid Chain

```json
{
  "chain": [
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9...",
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9...",
    "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiJ9..."
  ],
  "action": {"type": "read:calendar", "resource": "..."},
  "context": {"timestamp": 1735603300}
}
```

Validation result: `PASS`

## 8. Security Considerations

### 8.1 Chain Length Limits

Long chains increase attack surface. Implementations MUST enforce a maximum chain length (default: 10, hard limit: 20).

### 8.2 Cycle Detection

Implementations MUST detect cycles in the chain's principal sequence (root issuer, then each hop's `sub`) and reject with `CYCLE_DETECTED` if any principal repeats. This check runs at decide-time, alongside the depth limit above — not at issuance, since issuance can't see a chain's future hops.

### 8.3 Trust Decay

Longer chains imply weaker trust. See Trust Score Specification for chain length penalties.

### 8.4 Performance Degradation

Implementations MUST monitor validation time and alert if approaching limits. Consider caching validation results for repeated chains.

## 9. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
