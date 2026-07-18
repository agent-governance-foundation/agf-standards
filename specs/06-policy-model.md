# Specification 06: Policy Model and Versioning

**Version:** 0.2.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.0  
**Layer:** Core format  

## 1. Introduction

Policies define business rules for authorization. This specification defines the policy language, attachment model, evaluation semantics, versioning requirements, and conflict resolution.

## 2. Policy Language

### 2.1 Choice

For the reference implementation, policies are written in **Rego** (Open Policy Agent language). Rego is:
- Declarative
- Designed for policy
- Widely adopted
- Testable

Alternative languages (Cedar, OPA, custom) can be used with appropriate adapters.

The reference implementation evaluates Rego via OPA's REST API, falling back to a stub evaluator when no OPA server is reachable (e.g. local dev/test), so the decision path doesn't hard-depend on a running OPA instance.

### 2.2 Policy Structure

```rego
package agent_governance

# Default decision
default allow = false

# Rule: Allow if delegation chain is valid and risk acceptable
allow {
    valid_delegation_chain
    risk_score < 70
}

# Rule: Allow with caution for medium risk
allow_with_caution {
    valid_delegation_chain
    risk_score >= 70
    risk_score < 90
    requires_approval = false
}

# Risk score from trust evaluator
risk_score = input.risk_score

# Delegation chain validation status
valid_delegation_chain {
    input.chain_valid == true
    not input.revoked
}
```

### 2.3 Input Format

```json
{
  "action": {
    "type": "read:calendar",
    "resource": "calendars/alice@acme.com"
  },
  "subject": "did:example:agent:abc123",
  "trust_score": 75,
  "risk_score": 62,
  "chain_valid": true,
  "revoked": false,
  "depth": 3,
  "zone": "domain",
  "context": {
    "timestamp": 1735603300,
    "source_ip": "10.0.1.45"
  }
}
```

### 2.4 Output Format

```json
{
  "allow": true,
  "allow_with_caution": false,
  "deny": false,
  "reason": ["valid_delegation_chain", "risk_score < 70"]
}
```

## 3. Policy Repository

### 3.1 Storage

Policies stored in a Git repository (GitHub, GitLab, Bitbucket) with:

- Version history
- Pull request workflow
- Audit trail

The "Git repository" need not be an external host (GitHub/GitLab/Bitbucket) — a self-managed git repository that commits each policy write and returns the commit SHA satisfies version history and audit trail. The pull-request workflow can likewise be an internal state machine rather than a GitHub/GitLab PR — see §3.3.

### 3.2 Directory Structure

```
policies/
├── org/
│   ├── payroll/
│   │   ├── approve.rego
│   │   └── read.rego
│   ├── calendar/
│   │   └── access.rego
│   └── global/
│       └── base.rego
├── tests/
│   ├── payroll_test.rego
│   └── calendar_test.rego
└── data/
    ├── roles.json
    └── resources.json
```

### 3.3 PR Workflow, Canary Rollout, and Dry-Run

This section describes three additional capabilities of the policy lifecycle:

**PR-style review workflow.** Each policy carries a `pr_status` of `draft` → `open` → `merged` (or `rejected`). `POST /v1/policies/{id}/pr` opens it for review, `POST /v1/policies/{id}/pr/merge` merges (making it eligible for activation), `POST /v1/policies/{id}/pr/reject` rejects it. `GET /v1/policies/{id}/diff` returns a unified diff against the previous version (backed by version control), independent of the activation step in §6.5.

**Canary rollout.** `POST /v1/policies/{id}/canary` starts a sticky percentage-based rollout (1–99%) of a candidate policy alongside the current active one; `GET` reads the current canary state, `DELETE` stops it. `POST /v1/policies/{id}/rollback` reverts to the previously active policy.

**Policy dry-run.** `POST /v1/policies/{id}/dry-run` evaluates a candidate policy version against a supplied (or synthetic) decision input with no persistence, no HITL row creation, and no webhook dispatch — a genuine side-effect-free simulation, letting an operator see what a policy change *would* decide before activating it.

None of these three have full normative rules in this spec yet — state transitions, canary traffic-split semantics, and dry-run input schema remain to be formally specified.

## 4. Policy Versioning

### 4.1 Version Identifier

Every policy has a version:

```
{repository}/{path}/{rule}@{semver}
```

Example: `acme/policies/payroll/approve@1.2.0`

### 4.2 Version Strategy

| Version Component | Change Type |
|-------------------|-------------|
| Major | Backward incompatible rule changes |
| Minor | New rules, backward compatible |
| Patch | Bug fixes, no semantic change |

### 4.3 Policy Fetching

PDP fetches policies from repository using:

- Git clone (for local cache)
- OCI registry (for containerized policies)
- HTTP API (for hosted policy services)

### 4.4 Caching

Policies cached locally with configurable TTL:

- Default: 5 minutes
- After TTL: re-fetch from repository
- On fetch failure: continue using cached version with warning

## 5. Policy Attachment

### 5.1 Resource-Based

Policy attached to a specific resource:

```yaml
resource: "https://payroll.acme.com"
policy: "acme/policies/payroll/approve@1.2.0"
```

### 5.2 Action-Based

Policy attached to an action type:

```yaml
action: "approve:payment"
policy: "acme/policies/payments/approve@2.0.0"
```

### 5.3 Role-Based

Policy attached to a role:

```yaml
role: "finance-manager"
policy: "acme/policies/roles/finance@1.0.0"
```

## 6. Policy Evaluation

### 6.1 Evaluation Flow

```
Request → Fetch applicable policies → Build input → Evaluate Rego (OPA, stub fallback) → Return decision
```

### 6.2 Multiple Policies

A policy applies if ALL of the following match the request:

1. **Resource match:** Policy's `resource_pattern` matches the requested resource (wildcards supported: `https://payroll.acme.com/*`)
2. **Action match:** Policy's `action_type` matches the requested action
3. **Role match:** The agent's role (from DID document or context) is in the policy's `allowed_roles`

**Evaluation order when multiple policies apply:**

1. Collect all `allow` rules across all applicable policies
2. Collect all `deny` rules across all applicable policies
3. Apply decision logic:
   - If **any** deny rule matches → `DENY` (deny overrides allow)
   - Else if **any** allow rule matches → `ALLOW`
   - Else → `DENY` (default deny)

### 6.3 Zone Precedence (Trust Zones)

When policies from different trust zones conflict, the following precedence applies:

| Precedence | Zone | Rule |
|------------|------|------|
| 1 (highest) | Global | Deny overrides all; cannot be overridden |
| 2 | Domain | Deny overrides Local allow |
| 3 (lowest) | Local | Allow only if no higher zone denies |

**Zone precedence algorithm:**

```python
def resolve_zone_conflicts(global_result, domain_result, local_result):
    # Global deny wins unconditionally
    if global_result.get("deny"):
        return "DENY", "Global policy deny"

    # Domain deny overrides local allow
    if domain_result.get("deny"):
        return "DENY", "Domain policy deny"

    # Local allow only if no higher deny
    if local_result.get("allow"):
        return "ALLOW", "Local policy allow (no conflict)"

    # Default
    return "DENY", "No applicable allow rule"
```

### 6.4 Policy Version Conflicts

If two applicable policies are from different versions of the same rule, the newer version takes precedence. The PDP logs a warning and records both versions in the audit artifact.

**Example:**

```
Policy A (v1): allow if role=manager
Policy B (v2): deny if amount>100000 AND time=3AM

Request: role=manager, amount=150000, time=3AM

Policy A: allow → true
Policy B: deny  → true
Result:   DENY  (deny overrides allow)
```

### 6.5 Policy Version Evaluation

When a delegation token includes a `policy_version` claim (see Spec 01 §2.4):

1. The PDP MUST evaluate that exact policy version
2. If the policy version is not found, the PDP MUST NOT fall back to any other version — it MUST return `NOT_APPLICABLE` for the policy leg of the decision. The request is then decided on trust + risk alone (see Spec 04 / `authorization-flow.md` §10.1); it is never silently evaluated against a different org's or version's policy. This matters in multi-tenant deployments where a policy directory is shared across orgs: falling back to "whatever policy sorts last" would risk evaluating one org's request against a different org's Rego.
3. The decision artifact MUST record the requested version and that no policy was applied (`used_version: null`, or equivalent), never a fabricated "used" version
4. The decide response MUST surface the mismatch explicitly: `error_code: "POLICY_VERSION_NOT_FOUND"` together with `policy_version_requested` (the version asked for) and `policy_version_applied: null` (see Spec 10 §5.5). A `NOT_APPLICABLE` recorded only inside the artifact's policy block is not sufficient surfacing
5. The final decision MUST be capped at `ALLOW_WITH_CAUTION`: a trust+risk-only outcome under a missing requested policy version is a degraded-assurance state, following the same principle as the stale-revocation-list cap (Spec 05 §5.4). Kernel mapping: `ALLOW` + `caution` qualifier (Spec 00 §4.2)

**Audit artifact entry when no matching version is found:**

```json
"policy": {
  "requested_version": "acme/policies/payroll/approve@1.2.0",
  "used_version": null,
  "decision": "NOT_APPLICABLE",
  "note": "no fallback — decision made on trust + risk only"
}
```

## 7. Policy Testing

### 7.1 Test Structure

```rego
package agent_governance_test

test_allow_valid_request {
    input := {
        "chain_valid": true,
        "risk_score": 60,
        "revoked": false
    }
    allow with input as input
}
```

### 7.2 CI Integration

Policy changes MUST:

- Pass all tests
- Have two approvals
- Be signed by authorized committer

## 8. Example: Complete Policy

```rego
package payments

# High-value payment requires additional approval
default allow = false

# Allow standard payments
allow {
    input.action.type = "approve:payment"
    amount := parse_amount(input.action.resource)
    amount < 10000
    input.risk_score < 70
    input.chain_valid
}

# Allow with caution for medium payments
allow_with_caution {
    input.action.type = "approve:payment"
    amount := parse_amount(input.action.resource)
    amount >= 10000
    amount < 50000
    input.risk_score < 60
    input.chain_valid
    has_peer_approval(input.context)
}

# Deny high payments without executive approval
deny {
    input.action.type = "approve:payment"
    amount := parse_amount(input.action.resource)
    amount >= 50000
    not has_executive_approval(input.context)
}

parse_amount(resource) = amount {
    parts := split(resource, "=")
    amount := to_number(parts[1])
}

has_peer_approval(context) {
    context.approvals[_] == "peer"
}

has_executive_approval(context) {
    context.approvals[_] == "executive"
}
```

## 9. Security Considerations

### 9.1 Policy Integrity

Policies MUST be signed by authorized committers. PDP MUST verify signatures before loading.

### 9.2 Policy Injection

Policies should be treated as code. Use sandboxed evaluation (OPA's default is safe).

### 9.3 Version Pinning

Production PDPs MUST pin policy versions. Unpinned versions risk unexpected behavior and are prohibited in production environments.

**Pin management:**
- Pinned versions MUST be updated via the same CI/CD process as code changes
- Automated version updates without human review are prohibited
- Policy version changes require at least one approving review
- A rollback plan MUST exist for each policy update

**Example pinning:**

```yaml
# production-config.yaml
policy_pins:
  - resource: "https://payroll.acme.com"
    version: "acme/policies/payroll/approve@1.2.0"
  - resource: "https://calendar.acme.com"
    version: "acme/policies/calendar/access@2.1.3"
  - default: "acme/policies/global/base@3.0.1"
```

### 9.4 Conflict Detection

Implementations MUST detect and log policy conflicts. When a conflict is detected:

1. Log the conflict with both policy versions and outcomes
2. Apply zone precedence to resolve
3. If conflict remains unresolved (same zone, different outcomes), escalate to human review

## 10. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
| 0.2.0 | 2026-07-14 | §6.5: missing requested policy version must surface in the decide response (`POLICY_VERSION_NOT_FOUND`, `policy_version_requested`/`policy_version_applied`) and the decision is capped at `ALLOW_WITH_CAUTION` (KERNEL-NEG-03, RFC 0001) |
