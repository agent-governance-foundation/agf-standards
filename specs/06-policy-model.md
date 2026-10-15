# Specification 06: Policy Model and Versioning

**Version:** 0.4.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.3.0  
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

A stub evaluator may exist for local development and tests, but only when explicitly selected by configuration. It MUST NOT be used as a fallback for a configured policy when the policy engine is unreachable or returns an error (§6.7.2).

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

### 2.5 Evaluation Explainability

Decision responses that support it (§3.3 dry-run responses; real `/v1/decide` responses where an implementation chooses to extend this) MAY carry an `explain` field:

```json
"explain": [
  "rule 'allow' fired: valid_delegation_chain AND risk_score < 70",
  "rule 'deny' not evaluated: no matching clause"
]
```

Each entry is a human-readable statement of which rule fired, or was skipped and why.

`explain` MUST be omitted, never fabricated, when the underlying policy engine cannot produce an evaluation trace — e.g. an explicitly configured stub evaluator (§2.1), or an adapter for an alternative policy language that has no trace facility. An absent `explain` field means no trace was available; it is not an error condition.

Because §2.1 permits alternative policy languages (Cedar, custom) with their own adapters, this spec does not mandate a uniform trace event schema — only that each surfaced entry be a human-readable string.

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

**Policy dry-run.** Two dry-run modes exist, both side-effect-free (no persistence, no HITL row creation, no webhook dispatch):

#### 3.3.1 Candidate-policy dry-run

`POST /v1/policies/{id}/dry-run` evaluates a stored candidate policy version — identified by `{id}`, not the org's currently active policy — against a supplied decision input, letting an operator see what a policy change *would* decide before activating it.

**Input:**

| Field | Type | Required |
|---|---|---|
| `chain` | array of JWTs | yes |
| `action_type` | string | yes |
| `action_resource` | string | yes |
| `audience` | string | yes |
| `context` | object | no |

**Output:**

| Field | Type |
|---|---|
| `decision` | `ALLOW` \| `ALLOW_WITH_CAUTION` \| `DENY` \| `REVIEW_REQUIRED` |
| `matched_rules` | array of strings |
| `trust_score` | integer |
| `risk_score` | float |
| `evaluation_time_ms` | float |

*Informative.* A candidate dry-run (and an implementation's backtest that replays stored decisions against a candidate) evaluates the candidate in the engine and fails closed like any evaluation (§6.7). Such runs produce no signed Decision. An implementation MAY report implementation-specific failure states in the dry-run response, for example for a transient engine module whose use window lapsed; these states are not part of the Decision provenance of Spec 07 §3.3.

#### 3.3.2 Live dry-run

`POST /v1/decide` accepts an optional `dry_run: true` flag. Unlike §3.3.1, this evaluates the caller's request against the org's *currently active* policy, using the caller's real identity and delegation state — the same evaluation path a real decision would take, short-circuited before any side effect.

When `dry_run: true`:
- The PDP MUST NOT persist an audit artifact
- The PDP MUST NOT consume quota
- The PDP MUST NOT create an HITL approval row, even if the decision would otherwise be `REVIEW_REQUIRED`
- The PDP MUST NOT fire webhooks

The response carries the same shape as a real `/v1/decide` response, plus `simulated: true`, so a caller cannot mistake a dry-run result for a persisted decision.

PR-style review workflow state transitions and canary traffic-split semantics do not yet have full normative rules in this spec.

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
Request → Fetch applicable policies → Build input → Evaluate Rego (revision-bound, fail-closed: §6.6, §6.7) → Return decision
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

This rule does not apply between a pinned version and the organisation's mandatory policy. Those are always combined deny-overrides, whichever is newer (§6.5 item 1).

**Example:**

```
Policy A (v1): allow if role=manager
Policy B (v2): deny if amount>100000 AND time=3AM

Request: role=manager, amount=150000, time=3AM

Policy A: allow → true
Policy B: deny  → true
Result:   DENY  (deny overrides allow)
```

### 6.5 Policy Version Pinning

A request can name a policy version: in the decide request body (`policy_version`, Spec 10 §5.5) or as a delegation token's `policy_version` claim (Spec 01 §2.4). Naming a version is a **pin**. A pin never disables or replaces the organisation's policy.

**Mandatory organisation policy.** The organisation's policy that applies to the request is **mandatory**: the revision its active slot selects, or a matching attachment or canary slot (§6.6.3). The PDP MUST evaluate it for every decision to which it applies. Nothing a request or token carries can remove it or substitute another policy for it.

**Pin authorization.** The PDP MUST honour a pin only when it is **authorized**:
- **Token claim:** the claim originates in the chain's root token, and the root token is signed by a key the organisation has designated as a **pinning authority**, by an administrator action through a channel an agent identity cannot use. An agent identity's key MUST NOT be designated a pinning authority.
  - A later token that **repeats the root's claim unchanged** inherits the root's authorization, whoever signed it.
  - A later token that **introduces** a claim (the root carries none) or **changes** it is unauthorized: its only authority is its signer's own signature.
- **Request body:** the authenticated caller's credential carries the organisation permission `policies.pin`, granted by an organisation administrator. Credentials MUST NOT carry it by default. The permission authorizes **adding** a pin. It does not authorize removing or replacing a pin that the delegation chain carries.

Any other pin is **unauthorized**. That includes a claim introduced or changed in a token signed by an agent, and a body version from a caller without `policies.pin`. An agent's own signature is never pin authorization.

**Determining the pin.** Token claims are always checked, whether or not the body names a version. The PDP applies these steps in order, and the first that matches decides:
1. **Unauthorized:** any unauthorized claim in the chain, or a body version without `policies.pin`.
2. **Conflict:** an authorized chain pin and a body version that differ.
   - It is detected **before** either version is resolved, so it discloses nothing about whether either version exists.
   - A body pin cannot remove a restriction the delegation carries.
3. **One requested version:** otherwise there is exactly one: the authorized chain pin, the body version, or both when they are equal.
   - When the chain pin is present, its authorization is recorded as `organisation_authority`, including when the body repeats it.
   - The version is then resolved within the organisation (item 2 below), and is evaluated or rejected under items 1–4.

**When a pin outcome is determined.** The pin outcome is `unauthorized` or `conflict` once step 1 or 2 matches. For one requested version, it is `applied` or `not_found` once that version has been resolved. An outcome is never determined for a delegation chain that failed validation or carries a revoked token. Such a chain establishes no pin authorization.
- A decision whose pin outcome was determined records it (item 5). That includes a decision that a later failure also affects, for example a failed evaluation of the mandatory policy. A final `DENY` is not, by itself, grounds for omitting it.
- A decision that ended before any pin outcome was determined records no pin outcome. Examples: the delegation chain failed validation or carried a revoked token; or the mandatory selection could not be read before an authorized pin was resolved. The PDP MUST NOT record `unauthorized`, `conflict`, `not_found` or `applied` for an outcome it did not determine. The policy block still records the mandatory policy's provenance truthfully (Spec 07 §3.3).
- Either way, the named version remains in the decision's request record: the body's `policy_version`, and the delegation chain's tokens (Spec 07 §3.2). The absence of pin fields therefore does not mean that no version was requested.

**Outcomes:**

1. **An authorized pin of a version that exists for the organisation** is evaluated **in addition to** the mandatory policy, never instead of it. Both are evaluated, each bound to its own revision (§6.6.3 item 5) and each under §6.7, including fail-closed DENY. A pinned revision that is also the mandatory revision is evaluated once. The policy leg is **deny-overrides**:
   - DENY if either evaluation denies or fails;
   - otherwise the more restrictive of the two results, in the order `REVIEW_REQUIRED`, `ALLOW_WITH_CAUTION`, `ALLOW`. A `NO_OPINION` contributes nothing.

   §6.4 does not apply between a pin and the mandatory policy, whichever version is newer. A pin can tighten the outcome. It cannot loosen the mandatory policy. With no mandatory policy, the authorized pin is the only policy evaluated.
2. **No fallback, no disclosure.** A pinned version that does not exist selects no revision. The PDP MUST NOT fall back to any other version in its place, and does not query the engine for it. Versions are resolved only within the requesting organisation, so a version of another organisation is **not found**. It MUST be reported and recorded exactly as a version that does not exist, which keeps the existence of other organisations' versions undisclosed. Isolation applies to the rules actually evaluated, not only to the version selected (§6.6). This matters in multi-tenant deployments where a policy engine or directory is shared across organisations: falling back to "whatever policy sorts last" would risk evaluating one organisation's request against another organisation's policy.
3. **Where a mandatory policy applies**, a pin that is not found (item 2), unauthorized or in conflict gives a final decision of `DENY`. The policy leg is not run, and the PDP MUST NOT produce a trust-and-risk-only or other permissive outcome in its place. This outcome is recorded as `evaluation_status: not_evaluated` with the pin's status (Spec 07 §3.3).
4. **Where no organisation policy applies:**
   - an unauthorized or conflicting pin gives `DENY`, recorded as in item 3;
   - an authorized pin that is not found gives a policy leg of `NOT_APPLICABLE`. The request is then decided on trust and risk alone (see Spec 04 / `authorization-flow.md` §10.1). There is no organisation policy to bypass, and the same request without a pin receives the same trust-and-risk decision. The final decision MUST be capped at `ALLOW_WITH_CAUTION`: a missing requested version is a degraded-assurance state, following the same principle as the stale-revocation-list cap (Spec 05 §5.4). Kernel mapping: `ALLOW` with the `caution` qualifier (Spec 00 §4.2). This outcome is recorded as `requested_version_not_found` (Spec 07 §3.3), distinct from an organisation with no policy configured (§6.7.1).
5. **Recording.** When the pin outcome was determined (see above), the decision artifact MUST record:
   - the requested version;
   - the pinned version actually evaluated, or `used_version: null` when the pin was not applied, never a fabricated version;
   - the pin's status and, when applied, its authorization and the pinned evaluation's provenance (Spec 07 §3.3);
   - for a conflict: the body's version as the requested version, and the chain's version as `delegation_pin`.
6. **Surfacing.** When a pin is not applied, the decide response MUST surface it explicitly (Spec 10 §5.5):
   - `error_code: "POLICY_VERSION_NOT_FOUND"` (item 2), `"POLICY_VERSION_UNAUTHORIZED"` or `"POLICY_VERSION_CONFLICT"`;
   - `policy_version_requested` (the version asked for);
   - `policy_version_applied: null`.

   A `NOT_APPLICABLE` recorded only inside the artifact's policy block is not sufficient surfacing.

**Audit artifact entry for an authorized pin of a missing version, no organisation policy (item 4):**

```json
"policy": {
  "requested_version": "acme/policies/payroll/approve@1.2.0",
  "used_version": null,
  "pin_status": "not_found",
  "evaluator": "none",
  "evaluation_status": "requested_version_not_found",
  "decision": "NOT_APPLICABLE",
  "note": "no fallback — decision made on trust + risk only"
}
```

**Audit artifact entry for a conflict:** the chain carries an authorized pin of `…@1.2.0`, and the body names `…@1.1.0`:

```json
"policy": {
  "requested_version": "acme/policies/payroll/approve@1.1.0",
  "delegation_pin": "acme/policies/payroll/approve@1.2.0",
  "used_version": null,
  "pin_status": "conflict",
  "evaluator": "none",
  "evaluation_status": "not_evaluated"
}
```

**Audit artifact entry for an unauthorized pin (items 3 and 4):**

```json
"policy": {
  "requested_version": "acme/policies/payroll/approve@1.2.0",
  "used_version": null,
  "pin_status": "unauthorized",
  "evaluator": "none",
  "evaluation_status": "not_evaluated"
}
```

### 6.6 Policy Isolation and Revision-Bound Evaluation

A PDP that serves more than one organisation evaluates many organisations' policies with one policy engine. This section makes isolation a property of the **rules actually evaluated**, not only of which policy file or record is selected (§6.5 item 2).

#### 6.6.1 Isolation

1. A request MUST be evaluated only against the rules of the policy revision selected for the requesting organisation (§6.6.3). No other organisation's rules or data may influence the result.
2. Each revision MUST be evaluated in a namespace of its own. For Rego, that means each revision is loaded under a distinct package, and only that package is queried for it. Two organisations' policies MUST NOT be merged into one evaluated unit, even when their authors wrote the same package name.
3. A policy MUST be rejected when it is created if it references data outside its own namespace. The check MUST run on the policy engine's parsed representation, not on text, and covers:
   - direct references;
   - references through imports and aliases;
   - dynamically computed references;
   - overrides such as Rego's `with`.
4. A policy MAY use only built-in functions on an explicit allowlist, pinned to the policy engine version the PDP supports. Built-ins that can reach outside the evaluation (network, runtime introspection, module loading) MUST NOT be on the allowlist. The allowlist SHOULD be enforced with the engine's own capability mechanism where one exists. Changing the engine version requires re-reviewing the allowlist.
5. The PDP MUST reserve a rule-name prefix for its own use (§6.7.1), and MUST reject policies that define rules with that prefix.

#### 6.6.2 Immutable revisions

1. Each policy version that can be selected MUST be stored as an **immutable revision**: an identifier, the owning organisation, the original source, and the exact module text loaded into the engine (after any namespace rewriting), with a SHA-256 hash of each.
2. The stored module text is the source of truth when the engine has to be reloaded (§6.7.3). It MUST NOT be altered after creation. A PDP MUST refuse to load a revision whose module text no longer matches its recorded hash.
3. A revision MUST NOT be removed while any selection (§6.6.3) refers to it.

#### 6.6.3 Selection

1. A **selection slot** names the policy revision used for a class of requests:
   - the organisation's active policy;
   - a canary;
   - an attachment (§5).
2. A slot records:
   - the selected revision;
   - the slot's selection metadata (for a canary, its percentage; for an attachment, its action and resource patterns);
   - a version.
3. A slot's revision and its selection metadata MUST change together, atomically. A decision MUST NOT observe a new revision with the previous metadata, or the reverse.
4. A slot MUST be owned by exactly one organisation and MUST NOT select another organisation's revision. This SHOULD be enforced by the storage layer, not only by application checks.
5. **Revision-bound evaluation.** A decision MUST read its slot's selected revision once and evaluate exactly that revision. It MUST NOT query a shared or "current" policy location whose contents may differ from what was read.

#### 6.6.4 Changing a selection

1. Every change to a slot MUST be a compare-and-set against the version the caller read. A change against any other version MUST be rejected.
2. A slot's version MUST increase monotonically for the whole life of the slot, and MUST NOT reset. Clearing a slot (stopping a canary, removing an attachment) MUST leave the slot in a "not configured" state that keeps its version, so a request prepared against an earlier incarnation of the slot can never match a later one.
3. Every change MUST carry a caller-chosen **operation identifier**. The PDP MUST record each committed change with:
   - its operation identifier;
   - slot;
   - operation;
   - expected version;
   - target revision;
   - a canonical hash of the target selection metadata;
   - the resulting version.
4. When a change's outcome is uncertain (for example, the connection is lost at commit), the PDP MUST NOT report success. A retry repeats the operation identifier and the complete request. Then the PDP:
   - MUST look up the recorded change under the same mutual exclusion that serialises changes for that organisation, so it never concludes that an unresolved change did not commit;
   - MUST report the recorded outcome only if every recorded field equals the retried request;
   - MUST reject a reused identifier with any differing field;
   - MUST NOT infer success from the slot's current contents.
5. Before a change selects a revision, the PDP MUST confirm the engine holds that revision (§6.7.1 identity check). That confirmation and the change MUST NOT be separable by removal of the revision. Removal MUST take the same mutual exclusion as changes.

#### 6.6.4.1 Removing unreferenced revisions from the engine

1. The PDP MAY remove a revision from the engine once no slot selects it.
2. Because a decision evaluates the revision it read, which may since have been deselected, removal MUST wait for a retention horizon longer than the longest permitted interval between a decision reading its slot and its evaluation completing.
3. The PDP MUST enforce that interval with a deadline. A decision that would query the engine after its deadline MUST NOT query it, and MUST fail closed (§6.7.2, `deadline_exceeded`).
4. Any residual case where a revision is gone when queried (for example, a process stall after the final deadline check) MUST fail closed (`not_loaded`). It MUST NOT produce another revision's result.

### 6.7 Evaluation Outcomes and Failure

#### 6.7.1 Result classification

Each revision MUST carry a reserved identity rule whose value is the revision's identifier (for Rego, `__agf_revision := "<revision id>"`). The PDP classifies the engine's response to a query of a revision in the following order; the first matching row decides.

| # | Engine response | Classification | Policy leg |
|---|---|---|---|
| 0 | The decision's deadline (§6.6.4.1) passed before the query was sent; the query is not sent | failed: `deadline_exceeded` | DENY |
| 1 | No response within the query timeout | failed: `timeout` | DENY |
| 2 | Connection error | failed: `unreachable` | DENY |
| 3 | Error status from the engine | failed: `http_<status>` (or engine equivalent) | DENY |
| 4 | Body not parseable, or not an object | failed: `malformed` | DENY |
| 5 | No result member (the engine's answer for an undefined document) | failed: `not_loaded` | DENY |
| 6 | Result present but not an object | failed: `malformed` | DENY |
| 7 | Result lacks the identity rule | failed: `not_loaded` | DENY |
| 8 | Identity rule present but not a string | failed: `malformed` | DENY |
| 9 | Identity rule is a string other than the expected revision identifier | failed: `revision_mismatch` | DENY |
| 10 | Any of `allow`, `deny`, `allow_with_caution` present but not a boolean | failed: `malformed` | DENY |
| 11 | Otherwise | evaluated | `deny` true → DENY; else `allow_with_caution` true → ALLOW_WITH_CAUTION; else `allow` true → ALLOW; otherwise NO_OPINION |

**Failures before any engine response.** Two further failure states occur before the engine is queried, and are classified like the rows above (§6.7.2 applies to both):
- **`selection_unavailable`**: the decision's selection could not be read (for example, the store holding the slots failed). No revision was selected and the engine is not queried. The PDP MUST NOT fall back to another slot, to "no policy configured", or to any other revision. Policy leg: DENY.
- **`not_verified`**: a revision was selected, but before querying it the PDP could not confirm that the engine holds it, loaded and verified (§6.7.3: its module text matches the recorded hash and its identity rule returns the revision identifier). The engine is not queried. Policy leg: DENY.

- **NO_OPINION** means a configured policy legitimately expressed no decision. It merges with trust and risk exactly as `NOT_APPLICABLE` does (§6.1). It is recorded distinctly from "no policy configured" (Spec 07 §3.3).
- When the organisation has **no policy configured** for the request, the PDP does not query the engine for it, and the policy leg is `NOT_APPLICABLE`. An authorized pin is still evaluated (§6.5 item 1).

**Pinned versions** (§6.5). A pinned version is evaluated only when the pin is authorized, and always in addition to the mandatory organisation policy, never instead of it.
- **Authorized, and the version exists for the organisation:** its revision is a selected revision for this decision. Revision-bound evaluation (§6.6.3 item 5) and this section apply exactly as for any configured policy, including fail-closed DENY for every failure state. The mandatory policy, when there is one, is evaluated as well.
- **Not found (including another organisation's version), unauthorized or in conflict:**
  - no revision is selected for the pin, and the engine is not queried for it;
  - the PDP MUST NOT fall back to the organisation's active revision or any other in its place;
  - §6.5 items 3 and 4 govern the outcome;
  - the decision is never recorded as "no policy configured" (`not_configured`), and never as a failed evaluation.

#### 6.7.2 Failure is fail-closed

1. When a policy is configured for the request and its evaluation fails in any state of §6.7.1 (rows 0–10, `selection_unavailable` or `not_verified`), the decision MUST be DENY. A selection that could not be read is treated as configured: the PDP cannot establish that no policy applies.
2. It MUST NOT be REVIEW_REQUIRED: a human approval does not substitute for a policy that could not be evaluated.
3. The PDP MUST NOT substitute a stub, default or cached evaluation for a configured policy.
4. A stub evaluator MAY exist for development, but only when explicitly selected by configuration. A PDP configured for a real policy engine MUST refuse to start if the engine's address is not configured.
5. Each failure SHOULD be logged with the organisation, slot, revision and failure state, and counted per state.

#### 6.7.3 Readiness and engine restarts

1. A PDP MUST NOT report ready, and MUST NOT serve decisions, until every revision selected by any slot has been loaded into the engine and confirmed: its module text matches the recorded hash, and its identity rule returns the revision identifier.
2. If the engine loses revisions while the PDP is running (for example, an independent engine restart), affected decisions fail closed (`not_loaded`). The PDP MUST detect the loss, either from those failures or from a periodic comparison of selected and loaded revisions, and MUST reload from the stored module text (§6.6.2).
3. Organisations without a configured policy are unaffected.
4. The PDP MUST report not-ready while any selected revision is missing.

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
| 0.3.0 | 2026-09-07 | §3.3 split into §3.3.1 (candidate-policy dry-run, now formally specified with input/output schema) and §3.3.2 (new: live dry-run via `dry_run: true` on `/v1/decide`); added §2.5 Evaluation Explainability (`explain` field) |
| 0.4.0 | 2026-10-05 | Added §6.6 Policy Isolation and Revision-Bound Evaluation: isolation of the evaluated rules (a namespace per revision; no cross-namespace data references, checked on the parsed policy; pinned built-in allowlist; reserved rule-name prefix); immutable revisions with stored module text and hashes; selection slots whose revision and metadata change atomically, owned by one organisation; revision-bound evaluation; compare-and-set changes with monotonic, never-reset versions and operation identifiers, retries resolved under the same mutual exclusion against the complete recorded request; removal of revisions coordinated with changes, with an enforced decision deadline and retention horizon. Added §6.7 Evaluation Outcomes and Failure: revision identity rule and an ordered result classification; NO_OPINION distinct from no policy configured; fail-closed DENY (never REVIEW_REQUIRED) for every failure state; no stub, default or cached substitute for a configured policy; readiness gated on loaded, verified revisions; detection of and recovery from engine restarts. §2.1 no longer describes a stub fallback for configured policies; §6.5 item 2 points to §6.6. §6.5 rewritten as Policy Version Pinning: the organisation's applicable policy is mandatory and is never disabled or replaced by a requested version. A pin is honoured only when authorized: either the caller permission `policies.pin`, or a root-token claim signed by an organisation-designated pinning authority. An agent's own signature is never authorization. A later token repeating the root's claim unchanged inherits its authorization; an introduced or changed claim is unauthorized. A body pin that differs from an authorized chain pin is a conflict (`DENY`), detected before either version is resolved: the body cannot remove a delegation's pin. An authorized pin is evaluated in addition to the mandatory policy, deny-overrides; §6.4 does not apply to it. Another organisation's version is not found, and is reported identically. Where a mandatory policy applies, a pin that is not found, unauthorized or in conflict is DENY. With no organisation policy, an unauthorized or conflicting pin is DENY, and an authorized pin that is not found keeps the surfaced outcome capped at `ALLOW_WITH_CAUTION` (`requested_version_not_found`). §6.4 carve-out added. §6.1 and the `explain` note no longer describe a stub fallback. Amended (2026-10-07, draft): §6.7.1 failures before any engine response (`selection_unavailable`, `not_verified`); §6.7.2 item 1 covers them; §3.3.1 informative note on dry-run and backtest failure states. Clarified (2026-10-07, draft): §6.5 when a pin outcome is determined; a determined outcome is recorded even when a later failure affects the decision; a decision that ended before any outcome was determined records none, never an invented status; an invalid or revoked chain establishes no pin authorization; the named version stays in the request record. |
