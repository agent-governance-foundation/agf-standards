# Specification 02: Delegation Chain Semantics

**Version:** 0.5.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.3.0  
**Layer:** Core format  

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

The **acting principal** for a request is *extracted* from the **last token in the chain**, not the first:

```
claimed_subject     = chain[-1].sub
immediate_delegator = chain[-1].iss
```

`chain[0].iss` is the **root authority** (§2.1) and MUST NOT be used as the acting principal for chains of length > 1. A single-hop chain (`chain[0].iss` is also the immediate delegator) is the only case where root authority and immediate delegator coincide.

Three questions are answered separately and MUST NOT be collapsed into one identifier:

| Question | Answered by | Result |
|---|---|---|
| Who claims to be acting? | The token | **Claimed subject.** Untrusted. Evidence only: it remains in the signed `delegation_chain`. |
| Whose cryptographic authority validates the claim? | Signature verification (§3.4); issuer binding and trust (§3.10) | **Signature-verified subject.** The claimed subject of a chain that validated. It shows that trusted issuers delegated to that identifier. It does not show who is presenting the chain, that the subject is registered, or whom it belongs to. |
| Which organisation is entitled to recognise that identity? | The identity registry (Spec 08 §3.4) and, across organisations, the peering (Spec 26 §2.1), as applied by "Leaf subject ownership" in §3.10 | **Authenticated agent identity.** A signature-verified subject that satisfies §3.10 "Leaf subject ownership". |

**Persistent attribution** is any persistent record, and any downstream operation, that attributes, retrieves, exports, aggregates or erases data by agent identity. This includes, as examples and not as an exhaustive list: the audit artifact's `agent_id` (Spec 07 §3.1); the Authorization Decision Record's principal; SIEM and webhook exports; analytics and other aggregates; audit erasure by agent; behavioural reputation (Spec 04 §2.3.1); behavioural baselines and drift; HITL routing and escalation records (Spec 07 §11.3); discovery state; and per-agent environmental-signal history such as device sightings. Persistent attribution MUST use an authenticated agent identity only. Where none is established the attribution is `null` or absent. The decision itself is still evaluated and returned.

**Legacy records keep their meaning.** A record created before this rule retains the meaning it had when written. Its agent value is not rewritten and is not reinterpreted as an authenticated identity. An operation that retrieves, exports, aggregates or attributes by agent identity treats such a record as *attribution not established* unless that operation's own specification says otherwise. An operation that only removes data (erasure) MAY match a legacy record on its stored value, because failing to erase is the unsafe direction; that match is never evidence of authentication.

**An unauthenticated subject is still a valid subject.** A leaf subject that is not registered, or whose owner is not recognised for the requesting organisation (§3.10), does not make the chain invalid and does not change the decision. It means only that no authenticated agent identity exists for that request. A signature, a well-formed identifier or a registered issuer key never establishes one.

This is a normative rule, not an implementation detail: every subsystem that reads chain identity (reputation scoring, audit logging, HITL escalation, discovery) MUST apply it consistently.

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
- The header `kid` selects a **candidate** key only.
- The key that **actually verified** a token's signature MUST be a registered key of that token's `iss` identity (Spec 08 §3.4).
- This is checked for **every token**, against that token's own verifying key. It is not checked once per issuer, and not by resolving a key again afterwards.

A token whose verifying key is not a key of its issuer is rejected (`issuer_key_unbound`).

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

If any token contains a `max_depth` claim, the chain length (number of tokens) MUST NOT exceed `min(max_depth_i) + 1` (the first token counts as depth 0). `min(max_depth_i)` ranges only over tokens that explicitly carry a `max_depth` claim. If no token carries an explicit `max_depth` claim, the effective maximum depth is the default depth limit below, aligned with Spec 03 §4.2's Domain zone requirement (full-chain tracking up to depth 10). See §6 for the exact binding-limit computation.

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

### 3.9 JTI Uniqueness Within a Chain

A submitted chain MUST NOT contain two tokens with the same `jti`. Verifiers MUST reject such a chain with `INVALID_REQUEST` before scope evaluation. A duplicated token is either a replay artifact or a malformed chain; the continuity rules in §3.1 do not reliably catch self-referential duplicates.

### 3.10 Issuer Trust for the Requesting Organisation

A chain is always evaluated for a **requesting organisation**: the organisation that asks for the decision, revalidation, record or signature. The chain's **root** decides which issuers are permitted. Every token's issuer identity MUST be in the root's permitted set:

| Root issuer | Permitted issuers for every token of the chain |
|---|---|
| Owned by the requesting organisation (Spec 08 §3.4) | Only identities owned by the requesting organisation |
| The PDP's platform identity, when the root's subject is owned by the requesting organisation | The platform identity for the root; only identities owned by the requesting organisation for every later token |
| Owned by another organisation P, with an **active** peering between the requesting organisation and P (a cross-organisation decision, Spec 26 §2.1) | Only identities owned by the requesting organisation or by P |

A root owned by another organisation without an active peering is denied by Spec 26 §2.1's ordered checks.

**One peer per chain.** A chain has at most one permitted peer: the owner of its root. A peering between the requesting organisation and any other organisation, active or not, does not permit that organisation's issuers in the chain. It does not introduce another policy path either: only the root's peering can supply a federation selection (Spec 06 §6.8).

Any issuer outside the root's permitted set is rejected (`issuer_not_trusted`). In particular:
- A well-formed identifier and a verifiable signature do not establish trust.
- Platform signing does not establish trust for any organisation other than the root subject's owner. Platform-mediated federation beyond this requires its own specification.

**Missing or unreadable identities.**
- An issuer identity that is not registered is rejected (`identity_not_found`).
- One that cannot be looked up is rejected (`identity_unavailable`).
- Neither is ever skipped, treated as trusted, or relaxed in any environment. Development and test setups register the identities their fixtures use.

**Leaf subject ownership.** The table above constrains the chain's *issuers*. The leaf subject (`chain[-1].sub`) is not an issuer and is not covered by it. A leaf subject is an **authenticated agent identity** only if all of the following hold:

1. the chain passed validation under §3.4 and the issuer rules above;
2. the subject is registered in the identity registry (Spec 08 §3.4) and its record is active;
3. the subject is not the PDP's platform identity;
4. the subject's owner is the requesting organisation, or the chain's **permitted peer**.

The **permitted peer** is the owner P of the chain's root issuer, and only when P is not the requesting organisation and an **active** peering exists between the requesting organisation and P at the time of the decision. The following never make a subject authenticated, in any combination:

- a peering between the requesting organisation and any organisation other than the owner of this chain's root;
- a peering between P and any third organisation Q, or any relationship between Q and the requesting organisation;
- an inactive, suspended, pending or absent peering with P;
- a subject owned by P in a chain whose root is owned by the requesting organisation (that chain has no permitted peer).

Authentication is decided **per request and per chain**. It is not transitive, it is not carried from one chain or request to another, and it is not cached beyond the request that established it.

Ownership and peering MUST be established from the identity registry and the federation trust state (Spec 26 §2.1) only. They MUST NOT be taken from claims in a token, from the request body, or from any caller-supplied data. If the registry or the peering state cannot be read, no authenticated agent identity is established; ownership is never assumed.

A leaf subject that does not satisfy these conditions does **not** invalidate the chain: a leaf may be a DID that holds no key and is not registered. Decision outcomes are unchanged; only persistent attribution is `null` (§2.4).

**Scope.** These rules apply on **every path** that accepts a chain, or revalidates it, records it as verified, or signs on its basis. That includes:
- decisions;
- revalidation of offline decisions;
- Trust Summary issuance (Spec 24, Spec 26);
- proof retrieval.

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

The current implementation splits this across two layers: `validate_chain()` (signature and issuer checks, expiration, continuity, depth, scope, trust score) and an orchestrating decision service that calls it, then separately checks revocation and evaluates constraints.

`validate_chain()` is **not** free of I/O. Besides key resolution, the issuer checks of §3.4 and §3.10 read the identity registry (identity, owner, keys) and, for a cross-organisation chain, the peering. Any of those reads failing is a rejection (`identity_unavailable`, or Spec 26 §2.1's lookup failure), never a pass. The split keeps it free of revocation and constraint state, so it can be tested with registry and peering fixtures, without a revocation store or constraint context.

```python
# Layer 1: chain validation — no revocation or constraint state; reads keys, the identity registry and, cross-organisation, the peering (§3.4, §3.10)
def validate_chain(chain, action, audience, key_resolver, registry, requesting_org, current_time):
    effective_scope = None
    explicit_max_depths = []  # (token index, claimed max_depth) — only tokens that supply one

    if len(chain) > HARD_DEPTH_LIMIT:
        return error("MAX_DEPTH_EXCEEDED")

    for i, token in enumerate(chain):
        # 1. Verify signature, expiration, audience, required claims (incl. 90-day
        #    lifetime cap — Spec 01 §3.5), future-dated iat — one shared per-token check
        result = verify_single_token(token, audience, key_resolver, now=current_time)
        if not result.ok:
            return error(result.error.code, i)
        payload = result.payload

        # 1b. Issuer binding (§3.4) and trust for the requesting organisation (§3.10),
        #     for THIS token, against the key that actually verified it.
        identity = registry.lookup(payload.iss)   # unreadable -> identity_unavailable
        if identity is None:
            return error("identity_not_found", i)
        if result.verifying_key not in identity.keys:
            return error("issuer_key_unbound", i)
        if not trusted_for(identity, requesting_org, token_index=i, payload=payload):
            return error("issuer_not_trusted", i)

        # 2. Collect this token's explicit max_depth claim, if any. A token
        #    that omits the claim contributes no value to the binding
        #    minimum below — it is not treated as an implicit
        #    DEFAULT_MAX_DEPTH claim.
        claimed = payload.get("max_depth")
        if claimed is not None:
            explicit_max_depths.append((i, claimed))

        # 3. Update effective scope (with canonicalization)
        token_scope = set(canonicalize(s) for s in payload.scope)
        effective_scope = token_scope if effective_scope is None else effective_scope & token_scope

    # 3b. Binding depth limit is the smallest explicit max_depth anywhere in
    #     the chain. DEFAULT_MAX_DEPTH is used only when no token in the
    #     chain supplies an explicit max_depth claim.
    if explicit_max_depths:
        binding_index, effective_max_depth = min(explicit_max_depths, key=lambda pair: pair[1])
    else:
        binding_index, effective_max_depth = None, DEFAULT_MAX_DEPTH

    if len(chain) - 1 > effective_max_depth:
        return error("DEPTH_EXCEEDED", binding_index)

    # 4. Check continuity across the whole chain
    if not continuous(chain):
        return error("CHAIN_BROKEN")

    # 5. Check action against effective scope
    if canonicalize(action.scope) not in effective_scope:
        return error("SCOPE_INSUFFICIENT")

    return success(trust_score=calculate_trust_score(chain, current_time), effective_scope=effective_scope)


# Layer 2: orchestration (decide_service) — revocation, reputation, constraints
def decide(request, current_time):
    chain_result = validate_chain(request.chain, request.action, request.audience, key_resolver,
                                  registry, request.requesting_org, current_time)
    if not chain_result.valid:
        return deny(chain_result.error)

    # 6. Check revocation (separate injected port — see §3.3)
    if any_token_revoked(request.chain, revocation_port, current_time):
        return deny("REVOKED")

    # 7. Adjust trust score with behavioral reputation (Spec 04)
    adjusted_trust_score = max(0, chain_result.trust_score
                                  + reputation_penalty(authenticated_agent, requesting_org))   # 0 when none (Spec 04 §2.3.1)

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
| 0.2.0 | 2026-07-15 | Added §3.9: duplicate `jti` within a submitted chain is rejected with `INVALID_REQUEST` (CHAIN-11, KERNEL-NEG-02) |
| 0.3.0 | 2026-08-09 | §3.6/§6: corrected max_depth binding-limit pseudocode for chains with a mix of explicit and omitted `max_depth` claims — `min(max_depth_i)` ranges only over tokens that explicitly carry the claim; an omitting token never implicitly contributes `DEFAULT_MAX_DEPTH`. No change to the normative formula itself, and no effect on chains where every token supplies an explicit claim. |
| 0.4.0 | 2026-10-08 | Draft: §3.4 the key that actually verified each token must be a registered key of its issuer, checked per token against its own verifying key (`issuer_key_unbound`). Added §3.10 Issuer Trust for the Requesting Organisation: permitted issuers by root (requester-owned; platform root whose subject the requester owns; a root owned by an actively peered organisation), one peer per chain, `issuer_not_trusted`, `identity_not_found` and `identity_unavailable` in every environment; applies to decisions, offline revalidation, Trust Summary issuance and proof retrieval. §6 chain validation reads the identity registry and peering, and is no longer described as pure |
| 0.5.0 | 2026-10-31 | Draft: §2.4 distinguishes the claimed subject, the signature-verified subject and the authenticated agent identity, limits persistent attribution to the last, and states that legacy records keep their meaning; §3.10 adds leaf subject ownership and defines the permitted peer exactly (per request, non-transitive, only the owner of the chain's root under an active peering). An unregistered leaf remains a valid subject and does not change the decision. The reputation lookup in the orchestration pseudo-code uses the authenticated agent identity and the requesting organisation. |
