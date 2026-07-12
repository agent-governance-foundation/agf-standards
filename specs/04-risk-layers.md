# Specification 04: Risk Layers (Inherent, Environmental, Trust)

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.2

## 1. Introduction

Risk is not a single number owned by a single actor. This specification decomposes risk into three independent layers, each owned by a different authority, which combine to produce a final risk score.

## 2. The Three Risk Layers

### 2.1 Layer 1: Inherent Risk

**Definition:** Risk intrinsic to the action itself, independent of context or identity.

**Owner:** Domain authority (the organization that defines the action)

**Stability:** Changes slowly (when business processes change)

**Scale:** 0–100 (0 = no inherent risk, 100 = maximum inherent risk)

**Example Mappings:**

| Action | Inherent Risk | Rationale |
|--------|---------------|-----------|
| `read:calendar` | 10 | Read-only, non-sensitive |
| `read:payroll` | 60 | Sensitive but read-only |
| `write:document` | 30 | Modifiable but recoverable |
| `approve:payment<1000` | 40 | Financial but low amount |
| `approve:payment>100000` | 85 | High-value financial |
| `delegate:admin` | 95 | Privilege escalation |
| `delete:backup` | 90 | Data loss potential |

**Storage:** Inherent risk mappings stored in policy repository.

### 2.2 Layer 2: Environmental Risk

**Definition:** Risk derived from current context (time, location, velocity, anomalies).

**Owner:** Verifier (the system evaluating the request)

**Stability:** Changes with every request

**Scale:** 0–100 (modifier to inherent risk)

**Factors:**

| Factor | Risk Modifier | Example |
|--------|---------------|---------|
| Time of day | +0 to +30 | 3 AM action +20 |
| Location | +0 to +25 | Unusual geography +15 |
| Velocity | +0 to +40 | 10 actions/second +30 |
| Device | +0 to +20 | New device +10 |
| Anomaly score | +0 to +50 | ML model output |
| Constraint violation | configurable | See Spec 02 §3.7 |

**Formula:**

```
environmental_risk = sum(active_factors)  capped at 100
```

When a delegation token's `constraints` fail (see Spec 02 §3.7), a configurable penalty is added to environmental risk rather than resulting in an outright rejection. This allows risk-based decisions instead of binary pass/fail for borderline constraint violations.

### 2.3 Layer 3: Trust Risk

**Definition:** Risk derived from identity, delegation lineage, and revocation state.

**Owner:** Trust infrastructure (shared service)

**Stability:** Changes when delegations are created or revoked

**Scale:** 0–100 (higher = more trustworthy)

**Factors:**

| Factor | Trust Reduction | Example |
|--------|-----------------|---------|
| Delegation depth | −5 per level | Depth 3 → −10 |
| Delegation age | −2 per hour | 4 hours old → −8 |
| Revoked ancestor | −100 (invalid) | Parent revoked → 0 |
| Stale revocation list | −20 | Cache > 1 hour → −20 |
| Unknown issuer | −50 | Key not found → −50 |

**Trust Score Formula:**

```
trust_score = base(100) - depth_penalty - age_penalty - stale_penalty - unknown_penalty
trust_score = max(0, min(100, trust_score))
```

Revoked ancestor and unknown issuer are hard chain-validity gates checked before `trust_score` is computed (see Spec 02 §3.3, Spec 01 §3.1) — a hit means a hard `DENY`, not a soft point deduction. Stale revocation list does not apply where there is no revocation list with a staleness concept (see Spec 05). A separate, application-layer behavioral reputation penalty (0 to −25, based on the agent's recent decision history) MAY be applied on top of this structural formula.

## 3. Risk Combination

### 3.1 Final Risk Score Formula

The trust weight converts `trust_score` (0–100) to a multiplier (0–1).

**Linear weighting (default):**

```
trust_weight = trust_score / 100
final_risk   = inherent_risk + (environmental_risk × trust_weight)
```

**Non-linear weighting options:**

| Option | Formula | Effect | Use Case |
|--------|---------|--------|----------|
| Conservative | `(trust_score / 100)²` | Low trust → much lower weight | High-security: untrusted agents contribute almost no environmental risk; decision relies on inherent risk |
| Permissive | `sqrt(trust_score / 100)` | Low trust → higher weight | Resilient systems: even untrusted agents face stricter environmental scrutiny |

**Example (trust_score = 30, environmental_risk = 50):**

| Weighting | Trust Weight | Environmental Contribution | Final Risk (inherent = 40) |
|-----------|--------------|---------------------------|---------------------------|
| Linear | 0.30 | 15.0 | 55.0 |
| Conservative (square) | 0.09 | 4.5 | 44.5 |
| Permissive (sqrt) | 0.55 | 27.5 | 67.5 |

**Why conservative reduces environmental contribution:**
A compromised or untrusted agent cannot be relied upon to accurately report environmental context. Conservative weighting de-emphasizes environmental risk for low-trust sources; the system falls back to inherent risk (action-based, not agent-dependent) as the primary signal.

**Why permissive increases environmental contribution:**
An unproven agent faces stricter scrutiny. Environmental factors are amplified to compensate for the lack of established trust history.

Implementations MUST document their chosen weighting strategy. The default is linear. A deployment MAY layer per-org or per-tier overrides on top of the deployment-wide default; a conformant implementation of this spec only needs the deployment-wide default.

### 3.2 Decision Mapping

| Final Risk | Decision |
|------------|----------|
| 0–39 | `ALLOW` |
| 40–69 | `ALLOW_WITH_CAUTION` |
| 70–100 | `REVIEW_REQUIRED` |
| > 100 | `DENY` (cap at 100) — unreachable in practice |

Since `final_risk` is capped at 100 before this mapping runs (§3.1), the highest possible input is exactly 100, which falls in the `REVIEW_REQUIRED` row above — the `> 100` row can never actually be reached. `DENY` from risk score alone is therefore not a real outcome; `DENY` only ever comes from trust revocation/expiry or an explicit policy deny (see Spec 06).

## 4. Risk Layer Ownership

| Layer | Owner | Responsibility |
|-------|-------|----------------|
| Inherent | Domain authority (business team) | Define risk for each action type |
| Environmental | Verifier (security team) | Configure environmental factors |
| Trust | Trust infrastructure (platform team) | Calculate trust score |

**Why this separation:**

- Business teams know their data risk
- Security teams know environmental threats
- Platform teams manage identity trust

No single actor has complete control, preventing abuse.

## 5. API Representation

### 5.1 Inherent Risk Mapping

```json
{
  "action_type": "approve:payment",
  "conditions": [
    {"resource_pattern": "amount<10000", "risk": 30},
    {"resource_pattern": "amount>=10000", "risk": 60},
    {"resource_pattern": "amount>=100000", "risk": 85}
  ],
  "default_risk": 50
}
```

### 5.2 Environmental Risk Factors

```json
{
  "weighting": "linear",
  "constraint_violation_penalty": 30,
  "factors": [
    {"type": "time_of_day", "off_hours": ["22:00-06:00"], "penalty": 20},
    {"type": "velocity", "max_per_second": 5, "penalty_per_excess": 10},
    {"type": "location", "trusted_cidrs": ["10.0.0.0/8"], "untrusted_penalty": 15}
  ]
}
```

`weighting` options: `"linear"` (default), `"conservative"`, `"permissive"`

`constraint_violation_penalty`: added to environmental risk when a delegation's `constraints` fail (default: 30). Set to `null` to treat constraint violations as hard rejections instead.

### 5.3 Trust Score Response

```json
{
  "trust_score": 75,
  "components": {
    "base": 100,
    "depth_penalty": -10,
    "age_penalty": -8,
    "stale_revocation_penalty": 0,
    "unknown_issuer_penalty": -7
  },
  "lineage_depth": 3,
  "max_depth": 5,
  "age_hours": 4,
  "revoked": false
}
```

## 6. Example: Complete Risk Evaluation

### Request

- **Action:** `approve:payment/amount=150000`
- **Time:** 3:00 AM
- **Location:** VPN from unusual country
- **Delegation depth:** 4 hops
- **Delegation age:** 6 hours
- **Weighting:** linear

### Evaluation

**Inherent Risk:** 85 (payment > 100,000)

**Environmental Risk:**
- Time (3 AM): +20
- Location (unusual): +15
- Total: 35

**Trust Score:**
- Base: 100
- Depth (4 hops): −15 (3 extra × 5)
- Age (6 hours): −12 (6 × 2)
- Total: 73

**Risk Calculation (linear):**

```
Trust Weight               = 0.73
Environmental Contribution = 35 × 0.73 = 25.55
Final Risk                 = 85 + 25.55 = 110.55 → capped at 100
```

**Decision:** `REVIEW_REQUIRED` — a capped `final_risk = 100` falls in the 70–100 band per §3.2's decision-mapping table, not the unreachable `> 100` row.

**Reason:** "High inherent risk (85) combined with elevated environmental risk (35) and moderate trust (73) exceeds the ALLOW/ALLOW_WITH_CAUTION thresholds and requires human review before proceeding."

## 7. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
