# Specification 29: Enterprise Identity Assurance

**Version:** 0.4.0 (Draft)
**Status:** Working Draft — §4-18 (the identity-provider/binding/evidence data model, tenant discovery, domain verification, the Identity Assurance annotation, JIT provisioning, login policies, group→role mapping, break-glass accounts, the group-membership/lifecycle/audit foundation, SCIM provisioning, Enterprise Directory Integration/LDAP, Session Governance, Dynamic Roles and Permissions, and Passwordless Authentication/WebAuthn) has a reference implementation. SAML, IdP-initiated SSO, and certificate monitoring (§19) are out of scope for this version — SAML has a dedicated companion RFC as its own precondition-for-implementation gate.
**Supersedes:** None — new profile
**Layer:** Profile

## 1. Introduction

AAP-Core (Spec 00) defines **Actor** as "the human, service, or agent instance that acts," and its Decision object records policy version, trust score, and reasoning — but nothing about *how* a human actor authenticated before initiating the delegation that led to a decision. Spec 08 (Identity Registry) resolves *agent* identity — DIDs and their key material, the chain-of-custody concern for delegated authority once it exists. Neither spec addresses the step before that: verifying the human who is about to create or exercise authority, and carrying evidence of that verification into the eventual decision record.

This specification closes that gap for enterprise deployments: human authentication via an external, organization-managed Identity Provider (IdP) — OIDC in this version — and a compact, privacy-preserving annotation of that authentication carried into the signed decision artifact (Spec 07). It does not modify AAP-Core's six objects or their correlation rules; it defines an OPTIONAL enrichment of the existing Decision object's context, plus the supporting identity-provider/binding/evidence model that produces it.

## 2. Guiding Principles

**Authentication ≠ Authorization.** The IdP proves who authenticated. AGF decides what that identity may do. An implementation MUST NOT conflate the two — this specification defines only how authentication evidence is recorded and referenced, never how it factors into a policy decision (that remains entirely Spec 06's concern; §7.4 makes explicit that an identity-assurance lookup failure MUST NOT change the decision outcome).

**Federation, not migration.** An implementation MUST NOT store enterprise passwords. Identity remains at the IdP; this specification's data model stores only a trusted reference to it (§4.2) and evidence that a verification event occurred (§4.3), never the credential itself.

**Stateless-first.** An implementation MAY continue to use whatever stateless bearer-token model it already has (e.g. Spec 01's delegation tokens, or an analogous short-lived access/refresh token pair for human actors) unmodified, and this remains the default: an implementation that never enables §16's OPTIONAL session governance carries zero session-related state. §4.3's Authentication Evidence record is written once, at authentication time, and is never read or re-checked during authorization — it is audit evidence, not a live session gate, and remains so regardless of whether §16 is enabled. §16 defines the OPTIONAL live-session layer (token revocation, active-session listing, remote logout) for implementations that need it, deliberately kept a separate, additive object from Authentication Evidence rather than retrofitted into it — see §16.1 for why the two do not merge.

**Immutable evidence over live state.** Instead of asking "does this session still exist," an implementation answers "how was this identity authenticated, and what does the record show" — a question whose answer does not depend on any state that can later be deleted out from under an audit. §4.3 and §7 are both designed around this: append-only, no revocation field, no dependency on session lifetime.

## 3. Relationship to Other Specs

- **Spec 00 (AAP-Core):** this specification does not add a seventh kernel object. §7's Identity Assurance annotation is scoped, OPTIONAL context on an existing Decision object (§3.5's evidence payload) — an implementation conformant to Spec 00 alone remains fully conformant without ever producing one.
- **Spec 07 (Audit Trail and Decision Provenance):** §7 defines exactly where the annotation attaches within the already-normative signed evidence payload, and requires it be covered by the same signature as everything else in that payload — no separate signing path is introduced.
- **Spec 08 (Identity Registry):** disjoint by design. Spec 08 resolves DIDs for agents and workloads that carry delegated authority; this specification resolves human accounts authenticating via an enterprise IdP before any delegation exists. An agent acting under a delegation chain has no Identity Assurance annotation (§7.2); a human authenticating directly does.
- **Spec 13 (Privacy and Selective Disclosure):** §8's claims-hashing requirement and optional-retention model follow that spec's minimization principle, applied specifically to IdP-asserted claims.

## 4. Data Model

Three objects. Each has exactly one responsibility; a conformant implementation MUST keep them separate rather than merging fields across them, since §6 (tenant discovery), §7 (decision-time annotation), and §8 (privacy) each depend on being able to reason about one without the others.

### 4.1 Identity Provider

Authentication configuration for one connector, scoped to one organization.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | Provider identifier. |
| `organization_id` | string | Yes | Owning organization. |
| `connector_type` | string | Yes | `oidc` (§6) or `ldap` (§15) as of this version — note `ldap` providers do not use §6-8's authentication flow at all (§15.1). `scim` is not a distinct `connector_type`; it is a capability layered onto an existing provider (§14). `saml` is a reserved value an implementation MAY accept in storage for forward compatibility but MUST reject at connection time with a clear "not yet supported" error rather than silently no-op. |
| `connector_config` | object | Yes | Non-secret connector configuration. For `oidc`: `issuer`, `client_id`, `redirect_uri` are REQUIRED. |
| `display_name` | string | Yes | Shown to the user during tenant discovery (§6). |
| `is_default` | boolean | Yes | When an organization has more than one active provider, tenant discovery (§6) resolves to the default. |
| `enforce_sso` | boolean | Yes | When true, combined with `allow_password_fallback: false`, password-based authentication MUST be rejected for this organization (§6.3). |
| `allow_password_fallback` | boolean | Yes | Default true. The safety valve against a misconfigured `enforce_sso` locking out every admin (§6.3). |
| `status` | string | Yes | `active` \| `disabled`. |
| `certificate_expires_at` | string (ISO 8601) | No | Reserved for certificate-bearing connector types (SAML); unused by `oidc`. |
| `jit_provisioning_enabled` | boolean | Yes | Default `false`. See §9. |
| `default_role` | string | Yes | `owner` \| `admin` \| `viewer` (or a custom role name, §17.2), default `viewer`. The role a JIT-provisioned account receives absent a group-mapping match (§9, §11). |
| `login_policies` | object | Yes | Default `{}`. See §10. |

A connector's client secret (where applicable) MUST be stored encrypted at rest, separately from `connector_config`, and MUST NOT be returned in any response to any endpoint that reads this object back — not even to the organization that created it.

**Deletion:** an implementation MUST treat provider removal as a status transition (`status: disabled`), never a hard delete. §4.2's binding references a provider by id; a hard delete would either cascade-destroy every user's authentication history through it or leave dangling references, and there is no correctness reason to prefer either over simply disabling the provider going forward.

### 4.2 External Identity

A permanent, one-purpose binding: this AGF user corresponds to this subject at this issuer. Nothing else — no session state, no live claims.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | Binding identifier. |
| `organization_id` | string | Yes | Denormalized from the provider, for query convenience. |
| `user_id` | string | Yes | The AGF user this binding resolves to. |
| `provider_id` | string | Yes | The Identity Provider (§4.1) this binding was established through. |
| `subject` | string | Yes | The IdP's `sub` claim. |
| `issuer` | string | Yes | The IdP's `iss` claim. |
| `identity_type` | string | Yes | `human` in this version. |
| `email` | string | Yes | The email claim presented at first link. |
| `email_verified` | boolean | Yes | Whether the IdP asserted the email as verified. |
| `linked_at` | string (ISO 8601) | Yes | | 
| `last_login` | string (ISO 8601) | No | Updated on every subsequent authentication through this binding. |
| `status` | string | Yes | `active` \| `unlinked`. |

The tuple `(provider_id, subject, issuer)` MUST be unique — this is the lookup key on every authentication callback, and is what makes multiple providers, or a provider migration, representable without a schema change.

### 4.3 Authentication Evidence

An append-only record that an authentication event occurred. This is the object that replaces "session" in this specification's model (§2). An implementation MUST NOT expose any operation that updates or deletes an existing evidence record — the storage layer's own API surface, not merely a convention, is the right place to enforce this.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | Evidence identifier — this is the value carried in §7's annotation. |
| `external_identity_id` | string | Yes | The binding (§4.2) this evidence is for. |
| `authenticated_at` | string (ISO 8601) | Yes | |
| `authentication_method` | string | Yes | `oidc` in this version. |
| `mfa` | boolean | Yes | Best-effort, derived from the IdP's own `amr`/`acr` claims (§7.3) — not independently verified. |
| `assurance_level` | string | Yes | `aal1` \| `aal2` \| `aal3`, best-effort per §7.3. |
| `issuer` | string | Yes | |
| `claims_hash` | string | Yes | SHA-256 over the canonicalized raw claims (§8.1). MUST NOT be, or be reversible to, the claims themselves. |
| `ip_hash` | string | No | SHA-256 of the caller's IP address. An implementation MUST NOT store the raw IP here. |
| `device_hash` | string | No | |
| `country` | string | No | |
| `expires_at` | string (ISO 8601) | No | Informational only — an audit-retention horizon, never checked at authorization time. Absent by default. |

No `session_id`, no revocation field. Deleting or invalidating a live session, if an implementation has one at all, is entirely orthogonal to this record — the record documents that authentication happened; whether a subsequent bearer token derived from it is still valid is §16's concern, when an implementation enables it, never this record's.

### 4.4 Organization Domain

Domain-ownership verification, the prerequisite for tenant discovery (§6) to safely resolve an email to an organization.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | |
| `organization_id` | string | Yes | |
| `domain` | string | Yes | MUST be globally unique across all organizations — one organization owns a given domain, ever. |
| `verification_token` | string | Yes | |
| `verification_method` | string | Yes | `dns_txt` in this version. |
| `verification_status` | string | Yes | `pending` \| `verified` \| `failed`. |
| `verified_at` | string (ISO 8601) | No | |
| `verified_by` | string | No | The user who triggered a successful verification check. |

### 4.5 Role-Source Extension on the AGF User Object

This specification does not define the base user/account object — that
belongs to whatever implementation this profile sits on top of. It does,
however, require three fields on it, since §11's role-mapping sync
depends on being able to tell a manual role grant from an IdP-derived one:

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `role` | string | Yes | The *effective* role — unchanged in meaning from before this specification. Every existing reader of this field (authorization checks, token claims) continues to work unmodified. Where §17's optional dynamic-role model is implemented, this is the name of the `Role` object `role_id` (§17.2) resolves to, kept in sync for any reader that still only understands a role name (e.g. a token claim). |
| `role_source` | string | Yes | `manual` \| `idp`. Default `manual`. Governs whether §11's sync is allowed to overwrite `role` on login. |
| `idp_mapped_role` | string \| null | No | The most recent value §11's mapping computed, independent of `role_source`. Audit/troubleshooting visibility only — never itself the effective role. |

§11.2's manual-override-safety guarantee applies to `role`/`role_source` identically whether an implementation resolves roles from the fixed three-value set below or from §17's dynamic Role catalog — §17 changes the value space `role` is drawn from, never this section's synchronization rule.

### 4.6 Role Mapping

A rule translating an IdP-asserted group or claim into an AGF role.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | |
| `provider_id` | string | Yes | The Identity Provider (§4.1) this rule applies to. |
| `match_type` | string | Yes | `group` \| `claim`. |
| `match_key` | string | Yes | The claim name to inspect — default `groups` for `match_type: group`. |
| `match_value` | string | Yes | For `match_type: group`, a value that MUST appear in the named claim's list. For `match_type: claim`, a value the named claim's (stringified) scalar MUST equal. |
| `role` | string | Yes | `owner` \| `admin` \| `viewer`, or the name of an organization-scoped custom role (§17.2) where §17 is implemented. |
| `priority` | integer | Yes | Default `0`. Rules are evaluated in ascending order; the first match wins. |

## 5. Domain Verification

An implementation MUST reject any public/consumer email domain (the well-known set: `gmail.com`, `outlook.com`, `yahoo.com`, `hotmail.com`, and equivalents) at claim time, before a record is even created — two organizations cannot both plausibly own `gmail.com`, and allowing the claim would make tenant discovery (§6) ambiguous or spoofable. This check MUST reuse whatever free-email classification the implementation already applies to organization registration, rather than maintaining a second, divergent list.

**Method (`dns_txt`):** the implementation issues a random verification token and computes:

- Record name: `_agf-challenge.<domain>`
- Expected record value: `agf-domain-verify=<token>`

Verification is re-checkable and idempotent: an implementation MUST allow the check to be triggered repeatedly while an administrator propagates DNS, and MUST treat "no matching record found" (including DNS resolution failure or timeout) as `verification_status: failed`, not an error — a domain that fails a check today is not disqualified from succeeding on a later check with the same token.

## 6. Tenant Discovery

### 6.1 Resolution

Given a login email, an implementation resolves the identity provider to use as follows:

1. Extract the email's domain.
2. Look up an `OrganizationDomain` (§4.4) for that domain with `verification_status: verified`. If none exists, SSO is not available for this email — the caller falls back to whatever non-SSO authentication the implementation offers, or is told no path exists.
3. Within the resolved organization, select the `IdentityProvider` (§4.1) with `status: active` and `is_default: true`. If no provider is marked default, an implementation MAY fall back to the single active provider if exactly one exists.

### 6.2 Discovery Response

The discovery response MUST NOT reveal whether an email address itself is registered — only whether SSO is available for its domain, which is organization-level information the caller already implicitly has by knowing the domain.

| Field | Type | Description |
|-------|------|--------------|
| `sso_available` | boolean | |
| `provider_id` | string | Present only if `sso_available`. |
| `display_name` | string | Present only if `sso_available`. |
| `connector_type` | string | Present only if `sso_available`. |
| `enforce_sso` | boolean | Present only if `sso_available`. |

An implementation SHOULD rate-limit this endpoint distinctly from general API traffic — it is, by construction, a domain-enumeration oracle even though it reveals no per-email information.

### 6.3 Interaction with Non-SSO Authentication

When `enforce_sso: true` and `allow_password_fallback: false` on the resolved provider, an implementation MUST reject non-SSO (e.g. password) authentication for accounts in that organization, with an error that directs the caller toward SSO rather than a generic invalid-credentials response — the two failure modes have different remediations and MUST NOT be conflated in the response the caller sees. This MUST be enforced even for accounts that still hold a local credential from before `enforce_sso` was enabled.

Independently, an implementation MUST always preserve some non-SSO recovery path for at least one privileged account per organization (a "break glass" mechanism), regardless of `enforce_sso` — a misconfigured provider (wrong issuer, revoked client credentials at the IdP) MUST NOT be able to permanently lock an organization out of its own AGF account. `allow_password_fallback` (default `true`) is the coarse, provider-level safety valve; §12 defines the finer-grained, per-account break-glass mechanism.

## 7. Identity Assurance Annotation

This is the interoperability surface of this specification — the piece another AAP implementation (e.g. a client library) needs to understand even if it never implements enterprise SSO itself, because it may need to read this annotation off a decision artifact produced by an implementation that does.

### 7.1 Placement

The annotation is placed under `identity_assurance` inside the Decision object's context (the same context object Spec 04's environmental risk factors already populate), which an implementation MUST include within whatever portion of the decision artifact is covered by Spec 07's signature. An implementation MUST NOT attach this annotation anywhere in the artifact that falls outside the signed evidence payload — an unsigned identity claim is not evidence.

### 7.2 When Present

The annotation MUST be present only when the calling actor is a human authenticated via a binding this specification governs (§4.2), evidenced by a matching Authentication Evidence record (§4.3). It MUST be absent for: programmatic/API-key-authenticated calls, agent actors operating under a delegation chain with no directly-authenticated human principal, and any human principal whose most recent authentication has no corresponding Authentication Evidence record (e.g. authenticated by a mechanism this specification does not cover). An implementation MUST NOT fabricate or infer an assurance level in the absence of a real evidence record.

### 7.3 Shape

```json
{
  "identity_assurance": {
    "evidence_id": "...",
    "provider": "...",
    "subject": "...",
    "method": "oidc",
    "mfa": true,
    "aal": "aal2",
    "authenticated_at": "2026-07-18T10:30:00Z"
  }
}
```

| Field | Type | Description |
|-------|------|--------------|
| `evidence_id` | string | References §4.3's record. The pointer, not an inline copy — a verifier that needs more detail than this summary carries follows this reference through whatever authenticated audit channel the implementation offers, subject to §8's disclosure limits. |
| `provider` | string | The Identity Provider's `display_name` (§4.1) at the time of authentication. |
| `subject` | string | The `sub` claim (§4.2). |
| `method` | string | `oidc` in this version. |
| `mfa` | boolean | Best-effort, from the evidence record (§4.3). |
| `aal` | string | Best-effort assurance level, `aal1` \| `aal2` \| `aal3`. Derived from the IdP's own `amr`/`acr` claims where present (e.g. an `amr` value indicating a second factor, or a recognized `acr` value), defaulting to `aal1`/no-MFA when the IdP asserts neither. **This is a heuristic signal reflecting what the IdP chose to assert, not an independently verified assurance-framework certification** — an implementation MUST NOT represent this field as a compliance attestation beyond what the source IdP itself claims. |
| `authenticated_at` | string (ISO 8601) | From the evidence record. |

The annotation MUST NOT include raw IdP claims (name, groups, or any other claim beyond what this table lists) — §8 governs why, and where that information may live instead.

### 7.4 Failure Behavior

Producing this annotation requires a lookup (resolving the calling human's most recent Authentication Evidence record) that is not required for authorization itself. An implementation MUST treat a failure of that lookup as non-fatal to the decision — the decision MUST proceed and be signed exactly as it would if the actor's authentication predated this specification, simply without the annotation. This mirrors how an implementation SHOULD already treat any other best-effort context enrichment in the same decision pipeline (e.g. Spec 04's environmental signal collection): availability of an annotation is never a precondition for authorization to function.

### 7.5 Why This Matters

Without this annotation, an auditor asking "who authorized this action, and how confident are we that it was really them" can answer the first half from the Decision object's existing actor field, but not the second — assurance about the *authentication event itself* is otherwise not part of the auditable record at all, and would have to be reconstructed after the fact from IdP-side logs an AGF auditor may not have access to, correlated only by approximate timestamp. §7's annotation makes that correlation exact, signed, and self-contained within the artifact the rest of Spec 07 already governs — without embedding anything that widens the artifact's disclosure surface (§8).

## 8. Claims Handling and Privacy

### 8.1 Hash, Not Claims

Authentication Evidence (§4.3) stores `claims_hash` — SHA-256 over the canonicalized raw claims presented at authentication — never the claims themselves. This gives an implementation tamper detection (a claims set can be checked against the hash if independently obtained) without the retention liability of holding IdP-asserted PII (name, groups, and whatever else a given IdP chooses to assert) indefinitely as a side effect of normal authentication.

### 8.2 Optional Encrypted Retention

An implementation MAY additionally retain the raw claims, encrypted, in a record separate from Authentication Evidence, with a **default-off** configuration flag and a bounded retention window (this specification recommends 90 days, matching the default an implementation SHOULD apply when the feature is enabled without an explicit override). This MUST be a distinct storage object from §4.3, so that the common case (retention disabled) never creates the raw-claims record at all, and a deployment that never enables it carries none of the associated retention/deletion obligations.

### 8.3 What the Annotation Never Carries

§7.3 is exhaustive — no field beyond that table appears in the signed annotation. An implementation offering an authenticated audit surface for more detail (e.g. `email`, `email_verified` from §4.2) MUST apply organization-scoped access control equivalent to what it already applies to any other org-internal audit data; this specification does not create a new disclosure boundary, it inherits the one Spec 13 already establishes.

## 9. JIT Provisioning

§6.1/§7.2's baseline requires a prior invitation before a first-time binding
(§4.2) can be created — this section defines the OPTIONAL alternative.

When `IdentityProviderRow.jit_provisioning_enabled` (§4.1) is `true`, an
implementation MAY create a new account directly from a successful
authentication with no prior invitation, using the resolved organization's
domain verification (§5) as the trust boundary that replaces the
invitation — an account can only be JIT-provisioned into an organization
whose verified domain matches the authenticated email, so this MUST NOT be
enabled without §5 already being satisfied for tenant discovery to have
resolved the provider at all.

The new account's role MUST be: the result of §11's role-mapping evaluation
if any rule matches, else `default_role` (§4.1). Its `role_source` (§4.5)
MUST be `idp` — a JIT-provisioned account was never assigned a role by an
administrator, so there is nothing "manual" to protect (§11).

An implementation SHOULD record a distinct audit event for first-time JIT
creation, separate from routine login, so an administrator can see new
accounts appearing without an invitation as they happen.

## 10. Login Policies

`IdentityProviderRow.login_policies` (§4.1) is evaluated on every
authentication through that provider, after claims are verified and before
any binding/evidence work — a failing policy MUST reject the
authentication before any state changes.

```json
{
  "allowed_ip_ranges": ["10.0.0.0/8"],
  "blocked_countries": ["RU", "KP"],
  "allowed_countries": ["US", "CA", "GB", "IN"],
  "mfa_required": true
}
```

| Field | Type | Description |
|-------|------|--------------|
| `allowed_ip_ranges` | array of CIDR strings | When present, the caller's IP MUST fall within at least one range. If configured and the caller's IP cannot be determined, the implementation MUST reject the authentication rather than silently permit it — an implementation that bothered to configure this control is making a deliberate statement that unknown-IP callers are not welcome. |
| `blocked_countries` / `allowed_countries` | array of ISO country codes | Only evaluated when the caller's country is actually known. An implementation MUST NOT treat an unresolvable country (e.g. no geolocation capability configured) as a policy violation — that would silently lock out every login the moment one of these fields is set, on a deployment that never opted into geolocation at all. |
| `mfa_required` | boolean | The authentication's derived `mfa` value (§7.3) MUST be `true`, or the attempt is rejected. |

`device_trust_required` and `risk_score_threshold`, present in earlier
drafts of this specification, are deliberately absent — no device-trust or
human-login risk score is defined anywhere in this specification for a
policy to threshold against, and a field with no computable value behind
it is worse than no field at all.

IP-to-country resolution is intentionally unspecified by this
specification (an implementation MAY use an offline database or any other
method) but SHOULD prefer a method that does not transmit caller IP
addresses to a third party, consistent with §8's minimization principle.

## 11. Group→Role Mapping

### 11.1 Resolution

On every authentication (not only first-time linking), an implementation
evaluates the resolved provider's Role Mapping rules (§4.6) in ascending
`priority` order against the verified claims; the first rule whose
`match_value` is found (§4.6) determines the *mapped role*. If no rule
matches, there is no mapped role for that login.

### 11.2 Sync MUST NOT Overwrite a Manual Grant

This is the normative core of this section, and exists because of a
concrete failure mode: an administrator manually promotes a user to
`owner`; that user's IdP group has not yet caught up; on the user's very
next login, a naive sync would silently revert them to whatever the group
mapping computes. An implementation MUST NOT do this. Precisely:

- When a login produces a mapped role (§11.1), an implementation MUST
  always update `idp_mapped_role` (§4.5) to that value, regardless of
  `role_source`.
- An implementation MUST only overwrite the effective `role` (§4.5) with
  the mapped role when `role_source == "idp"`.
- When `role_source == "manual"`, a mapped role MUST be recorded in
  `idp_mapped_role` for administrator visibility but MUST NOT change
  `role`. The divergence itself (`role` manually set to `owner` while
  `idp_mapped_role` currently says `viewer`) is the audit signal an
  administrator needs, not a defect to reconcile automatically.
- Any administrative action that manually sets a user's `role` MUST also
  set `role_source = "manual"` in the same operation — this is the actual
  mechanism that prevents the failure mode above; setting `role` without
  also setting `role_source` reopens it.
- An implementation SHOULD offer an explicit action to revert
  `role_source` back to `"idp"` (immediately re-applying `idp_mapped_role`
  if present), so a manual override is a deliberate, reversible choice
  rather than a one-way trapdoor.

### 11.3 First-Time Linking

For JIT-provisioned accounts (§9), the mapped role takes precedence over
`default_role`. For invitation-accepted accounts, the mapped role takes
precedence over the invitation's administrator-assigned role as well — an
active, configured group mapping is a deliberate ongoing policy an
administrator opted into, and MUST take precedence over what may be a
stale role choice made once, at invitation time.

## 12. Break-Glass Accounts

### 12.1 The Gap This Section Closes

A password-reset flow that does not check `enforce_sso` (§6.3) is not a
break-glass mechanism — it is an unintended, silent, unaudited bypass of
the organization's SSO policy, available to *any* account, not a
deliberately designated one. An implementation MUST NOT allow this: the
password-reset/forgot-password flow MUST reject issuing or redeeming a
credential-setting token for an account whose organization enforces SSO
(§6.3), unless that specific account is designated break-glass (§12.2).

### 12.2 Designation

An account MAY be designated `is_break_glass` (§4.5's user-object
extension list gains one more field here: `is_break_glass: boolean`,
default `false`). Only a break-glass account is exempt from §6.3's
password-login rejection and from §12.1's reset restriction. Designation
MUST be restricted to the same privilege level an implementation already
requires for organization-owner-level actions.

### 12.3 Audit

A successful password-based login by a break-glass account, while its
organization enforces SSO, MUST be recorded as a distinct event type from
routine login — this is the signal an administrator needs to see rarely
and needs to be able to find quickly when it happens. An implementation
SHOULD notify other administrators when it occurs, though this
specification does not mandate a specific notification channel.

## 13. Group Membership Foundation

Prerequisite for §14/§15: group membership from any source must be
separable from the role it produces, so an implementation can always
answer "what did the source assert" independently of "what role AGF
computed from it." Feeding a directory source's group data directly into
role assignment (skipping this record) would make that separation
impossible and would give SCIM/LDAP no way to converge on the same
mechanism §11 already defines for OIDC.

### 13.1 External Group Membership

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | |
| `external_identity_id` | string | Yes | The binding (§4.2) this membership belongs to. |
| `provider_id` | string | Yes | |
| `group_id` | string | No | The source's stable group identifier, when it has one. |
| `group_name` | string | Yes | The matchable value (§11's `match_value`) — always present regardless of source. |
| `source` | string | Yes | `oidc` \| `scim` \| `ldap`. |
| `last_seen` | string (ISO 8601) | Yes | |

The tuple `(external_identity_id, group_name)` MUST be unique. An
implementation MUST upsert into this record from every source that
observes membership: an OIDC login's `groups` claim, a SCIM group
PATCH/PUT, an LDAP sync sweep. §11's `resolve_mapped_role()` reads
`group_name` values from here — not from a claims dict, not from
whatever a directory source most recently returned — for `match_type:
group` rules. `match_type: claim` rules remain claims-only (§11.1), since
SCIM/LDAP have no equivalent structure.

### 13.2 Identity Lifecycle

`ExternalIdentityRow.status` (§4.2, originally `active | unlinked`)
expands to a 5-state lifecycle: `pending | active | suspended | unlinked
| archived`.

| State | Meaning |
|-------|---------|
| `pending` | Known from a directory source but not yet allowed to authenticate (e.g. a SCIM user created with `active: false`). |
| `active` | Linked to an account, may authenticate. |
| `suspended` | Temporarily blocked (e.g. SCIM `active: false` on an existing user) — reversible, distinct from `unlinked`. |
| `unlinked` | No longer present at the source (SCIM `DELETE`, absent from an LDAP sweep) — the binding is preserved for audit, never hard-deleted. |
| `archived` | Reserved for future retention tooling; no behavior is specified for it in this version. |

`provisioned` and `linked` are deliberately not separate states: this
specification's provisioning mechanisms (§9, §14, §15) all create the
account and its binding in one atomic step, so there is no separately
observable moment between them for a state transition to mark.

### 13.3 Identity Audit Events

An implementation SHOULD emit a distinct, dot-namespaced event for each
lifecycle-relevant action: `identity.provisioned`, `identity.updated`,
`identity.group.changed`, `identity.deprovisioned`, `identity.linked`,
`identity.unlinked`, `identity.sync.started`, `identity.sync.completed`,
`identity.sync.failed`. This specification does not mandate a specific
audit-event transport — whatever mechanism an implementation already uses
for other identity events (§9's JIT-provisioning event, §12.3's
break-glass event) is sufficient, provided the event type strings
distinguish these actions from each other.

## 14. Enterprise Provisioning (SCIM)

An OPTIONAL capability layered onto an existing Identity Provider (§4.1),
regardless of its `connector_type` — mirrors how real IdPs pair SCIM
provisioning with the same application registration that already handles
authentication, rather than requiring a second provider record.

### 14.1 Scope

This specification does not require full SCIM 2.0 (RFC 7644) compliance —
only the operations and shapes real SCIM clients (Okta, Entra ID)
actually send:

- User and Group resource CRUD, including `ServiceProviderConfig`.
- Filtering: `filter=userName eq "..."` and `filter=externalId eq "..."`
  only. An implementation MUST reject any other filter operator or
  attribute with an explicit error, never by silently ignoring the filter
  or treating it as a no-match.
- PATCH: the `Operations` array shapes for `active`, `name`, `emails` (User)
  and `members` add/remove (Group) — including the path-less
  `{"op": "replace", "value": {"active": false}}` form some IdPs send for
  deactivation, alongside the path'd form.
- `DELETE` on a User MUST NOT hard-delete — it transitions the binding to
  `unlinked` (§13.2), consistent with every other identity-removal
  operation this specification defines.

### 14.2 Authentication

A SCIM client authenticates with a bearer token scoped to exactly one
Identity Provider — not a general-purpose credential, and not further
scoped by anything in the request URL or body. An implementation SHOULD
support minting, naming (for administrator recognition — an unlabeled
token becomes unidentifiable within months), and revoking/rotating this
token independently of the provider's other configuration.

### 14.3 Group Membership

A Group PATCH/PUT's member list MUST be written to External Group
Membership (§13.1) — never directly to a user's role. Role assignment
happens exclusively through §11's existing resolution path, re-evaluated
after the membership write, with §11.2's manual-override-safety guarantee
applying identically regardless of whether the triggering event was a
login or a provisioning action.

## 15. Enterprise Directory Integration (LDAP/AD)

Read-only directory synchronization — **not** an authentication
mechanism. This specification uses "Enterprise Directory Integration"
rather than "LDAP/Active Directory" deliberately: LDAP is the protocol,
Active Directory is one deployment of it, and this section applies
equally to OpenLDAP, 389 Directory Server, FreeIPA, or any other
LDAP-speaking directory without redefinition.

### 15.1 Scope

An implementation periodically searches a configured directory for users
and groups, and provisions/updates/deprovisions AGF accounts and group
membership (§13.1) accordingly. It MUST NOT validate an end user's login
credentials against the directory (no LDAP bind-as-authentication) —
users provisioned this way authenticate through an already-configured
OIDC connector (§9's normal flow) or password, exactly as any other
account does. An implementation's setup documentation MUST state this
boundary explicitly, since "directory sync" is easily mistaken for "you
can now log in with your directory password."

### 15.2 Deployment Prerequisite

A hosted implementation of this specification is commonly deployed
separately from the directory it synchronizes against (e.g.
cloud-hosted service, on-premises Active Directory behind a firewall).
Network reachability between the two is a deployment prerequisite this
specification does not solve — an implementation MUST document this
requirement rather than silently assuming a connection will succeed.

### 15.3 Sync Behavior

- Sync MUST run on a schedule, and MAY additionally be triggered
  on-demand. Both triggers MUST use the same underlying sync logic — an
  implementation MUST NOT maintain two divergent code paths for
  "scheduled" vs. "manual" sync.
- Each configured directory source MUST be synced independently, with
  failure isolation: one source being unreachable MUST NOT prevent any
  other source's sync from completing.
- A user present in a previous sync but absent from the current one MUST
  be transitioned to `unlinked` (§13.2) — not hard-deleted.
- Provisioning reuses the same account-creation mechanism as §9/§14 — an
  implementation MUST NOT maintain a third, separate user-creation code
  path for directory-sourced accounts.

## 16. Session Governance

### 16.1 Relationship to Authentication Evidence

This section defines an OPTIONAL, additive layer — a live, mutable Session object, distinct from and layered on top of §4.3's Authentication Evidence, never merged into it. The two answer different questions with different lifecycle requirements: Evidence answers "how was this identity authenticated, and what does the record show" and MUST remain append-only, with no field an implementation can later change or clear (§2, §4.3). Session answers "is a bearer token derived from that authentication still valid right now" — a question whose answer changes over time by design (rotation, revocation, expiry), which is exactly why it MUST NOT live on the append-only record. An implementation that never enables this section keeps §2's stateless-first default entirely unmodified; Authentication Evidence continues to exist, and continues to record real authentication events, whether or not Session Governance is ever turned on.

### 16.2 Token Revocation (`token_version`)

An implementation SHOULD maintain a monotonically-increasing integer on the user/account object (`token_version`, default `0`) and embed its value as a claim in every access and refresh token issued to that account. Token validation MUST reject a token whose embedded `token_version` does not match the account's current value — this is the mechanism by which an implementation invalidates an already-issued, not-yet-expired token, which a purely stateless bearer-token model (§2's default) has no way to do at all.

An implementation MUST bump `token_version` at minimum when: an account's credential changes (password change/reset), and when the account holder explicitly requests invalidating every other active session ("log out everywhere"). Bumping `token_version` is a coarser instrument than per-session revocation (§16.3) — it invalidates every outstanding token for the account in one step, including ones the account holder may not know exist, which is exactly the property a credential-compromise response needs.

This mechanism is independent of §16.3: an implementation MAY support token-version revocation without persistent sessions, MAY support both together, but MUST NOT treat one as a substitute for the other — a compromised refresh token surviving a password change because the implementation only tracked it in a Session record it forgot to revoke is exactly the failure mode this section closes.

### 16.3 Persistent Sessions

An implementation MAY additionally offer a persistent Session object, gated behind an explicit, organization-level opt-in (default OFF) — session tracking is real additional infrastructure and audit surface an organization SHOULD choose deliberately, not inherit silently the moment this section is implemented.

**Session object:**

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | Session identifier. |
| `user_id` | string | Yes | The account this session belongs to. |
| `authentication_method` | string | Yes | `password` \| `oidc` \| `webauthn` (§18) \| `break_glass`. An implementation MAY extend this set for other first factors it supports (e.g. `saml`, once implemented per §19), but MUST keep each value protocol-specific rather than reusing one generic value (e.g. `"sso"`) once more than one federated protocol exists — otherwise this field can no longer distinguish which protocol actually authenticated the session. Best-effort/audit, never itself an authorization input. |
| `device_name` | string | No | Best-effort, derived from request metadata (e.g. user-agent) at session creation. Display-only — an implementation MUST NOT use this field, or anything derived from it, as a security input; it is trivially spoofable by the caller. |
| `refresh_token_hash` | string | Yes | A hash of the current refresh token, never the token itself. |
| `created_at` | string (ISO 8601) | Yes | |
| `last_active_at` | string (ISO 8601) | No | Updated on each successful token refresh through this session. |
| `revoked_at` | string (ISO 8601) | No | Set on explicit revocation (§16.5) or on the reuse-detection response (§16.4). |

**Creation:** a session MUST be created at successful authentication, for every first-factor mechanism an implementation supports (password, SSO/OIDC, WebAuthn per §18, break-glass) — an implementation MUST NOT create sessions for only some authentication paths while silently exempting others from the same audit/revocation surface; if a given authentication path cannot yet create a session, that MUST be a stated, temporary implementation gap, not a permanent design choice.

### 16.4 Refresh Rotation and Reuse Detection

Each use of a refresh token MUST atomically rotate `refresh_token_hash` to a newly-issued token's hash before returning that new token to the caller — the previous token becomes invalid for any subsequent use the instant rotation succeeds, not merely "eventually."

Presenting a refresh token whose hash does not match the session's *current* `refresh_token_hash` — i.e., a token from earlier in the rotation chain, not merely the most recent one — MUST be treated as reuse and MUST revoke the *entire session* (setting `revoked_at`, invalidating every token derived from it), not only the presented stale token. Reuse of an old refresh token is a signal that the token was captured and is now being replayed by an attacker racing the legitimate holder; revoking only the single reused token would leave whichever party (attacker or legitimate holder) currently holds the *latest* rotated token still authenticated, which defeats the purpose of detecting reuse at all.

### 16.5 Capabilities

Where §16.3 is enabled, an implementation SHOULD expose:

- Self-service: list the calling account's own active sessions (at minimum `device_name`, `created_at`, `last_active_at`); revoke one session; revoke all sessions (a "log out everywhere" action, which SHOULD also bump `token_version` per §16.2 — belt-and-suspenders against any session the revocation itself might race).
- Administrative oversight: for a privileged caller within the same organization, the equivalent list/revoke-one/revoke-all operations targeting another member's sessions. An admin's own "revoke all" of another user MUST NOT be assumed to exempt the admin's own session if the admin revokes their own account's sessions by the same mechanism — an implementation MUST apply the same reuse-safe revocation semantics (§16.4) regardless of whose session is being closed.
- A credential change (password change) SHOULD revoke the account's active sessions as part of the same operation, not merely bump `token_version` — both mechanisms MUST fire together for a credential-compromise response to be complete (§16.2).

## 17. Dynamic Roles and Permissions

### 17.1 Motivation

§4.5/§4.6/§9/§11 above describe role assignment against a fixed three-value set (`owner` \| `admin` \| `viewer`). This section defines an OPTIONAL, backward-compatible replacement: a data-driven Permission/Role model that an implementation MAY adopt without changing the meaning of anything already normative above. Every MUST in §9/§11/§12 that references "the role" continues to hold exactly as written, whether the value space behind it is the fixed three-value set or this section's dynamic catalog.

### 17.2 Data Model

| Object | Fields | Notes |
|--------|--------|-------|
| Permission | `id`, `key` (e.g. `team.invite`), `description` | The catalog. An implementation MUST NOT define a permission for a capability it does not actually gate somewhere in its own code — an ungated permission is a promise the implementation cannot keep, and is worse than the permission not existing. |
| Role | `id`, `organization_id` (nullable), `name`, `is_built_in` | `organization_id: null` denotes a built-in role shared across every organization; non-null denotes a role scoped to exactly one organization (a "custom role", OPTIONAL). |
| RolePermission | `role_id`, `permission_id` | Join table — the grant. |

An implementation adopting this section MUST seed built-in roles that reproduce the pre-existing three-tier behavior exactly as a default: `owner` holding every defined permission, `viewer` holding none, and `admin` at whatever practical subset the implementation's own pre-existing `owner`-only gates already implied — adopting this section MUST NOT itself change what any existing account can do.

`role` (§4.5) is denormalized from `role_id` for any reader that only understands a role name (most importantly, a bearer-token claim, which SHOULD NOT require a database lookup to decode) — an implementation MUST keep the two in sync on every write, never let `role` and the object `role_id` points to diverge.

### 17.3 Custom Roles

An implementation MAY allow an organization to define additional, organization-scoped roles, each granted an arbitrary subset of the Permission catalog (§17.2). Where offered:

- Creating, modifying, or deleting a custom role SHOULD itself be gated by a dedicated permission (e.g. `roles.manage`) — role management is itself a capability this catalog can describe, not a special case above it.
- Deleting a role currently assigned to any account MUST be rejected with a clear, distinct error — an implementation MUST NOT silently cascade the deletion into an undefined or null role for those accounts.
- An implementation SHOULD reserve the built-in `owner` role specifically from ever being assignable by name through the same path a custom role is assigned — matches whatever elevated, owner-specific safeguards (e.g. "cannot remove the last owner") the implementation already applies to that role and does not want a custom-role path to bypass.

### 17.4 Interaction with §11's Role Mapping

§11's resolution and §11.2's manual-override-safety guarantee are unmodified by this section: a Role Mapping rule's `role` (§4.6) simply names a value from whichever space is in effect (fixed three-value, or this section's catalog including any custom roles) — §11's sync logic has no awareness of, and no dependency on, which.

### 17.5 Non-Goals (This Section)

Deliberately out of scope for this version of dynamic roles: role inheritance/hierarchy between custom roles, multiple roles held simultaneously by one account, delegating a role or its permissions to an agent identity (that is Spec 06/08's delegation-chain model — a disjoint mechanism this specification does not touch, not merely a deferred extension of this one), and condition-based or assurance-level-gated permissions (e.g. "this permission requires an `aal2` authentication," which depends on assurance data this specification defines in §7 but does not yet wire into permission evaluation anywhere).

## 18. Passwordless Authentication (WebAuthn)

### 18.1 Scope

An OPTIONAL first-factor authentication mechanism using the WebAuthn/FIDO2 standard ("passkeys"), additive to an account that already exists via password or SSO — a credential is registered *after* an existing authenticated session, the same posture this specification already uses for other account-security enrollments. A passwordless-only signup path (creating a new account with no password at all) is out of scope for this version.

### 18.2 Data Model

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | |
| `user_id` | string | Yes | The account this credential is registered to. |
| `credential_id` | string | Yes | The authenticator-assigned credential identifier (base64url). MUST be unique across all accounts. |
| `public_key` | string | Yes | The credential's public key (COSE format, base64url). |
| `sign_count` | integer | Yes | The authenticator's signature counter, as last observed (§18.6). |
| `transports` | array of string | No | Informational (e.g. `internal`, `hybrid`) — never a security input. |
| `device_name` | string | Yes | Best-effort display label, same posture as §16.3's `device_name` — MUST NOT be used as a security input. |
| `created_at` | string (ISO 8601) | Yes | |
| `last_used_at` | string (ISO 8601) | No | |

This object intentionally does not extend §4.2/§4.3 (External Identity / Authentication Evidence) — those are structurally coupled to federated, IdP-mediated authentication (`external_identity_id`, `issuer`, `subject`). A WebAuthn credential authenticates directly against this implementation, with no external IdP in the loop, so a passkey login does not produce an Authentication Evidence record and §7's `identity_assurance` annotation remains absent for it — the same, already-normative outcome §7.2 specifies for "any human principal whose most recent authentication has no corresponding Authentication Evidence record." An implementation MUST NOT fabricate an Evidence record for a passkey login merely to produce an annotation.

### 18.3 Registration and Authentication Ceremonies

Both ceremonies (registration — binding a new credential; authentication — using one to log in) proceed in two request legs, consistent with WebAuthn's `navigator.credentials.create()`/`.get()` browser flow. An implementation MUST carry ceremony state (the challenge) between the two legs via a short-lived, single-use, signed token scoped to that ceremony — MUST NOT require server-side challenge storage, keeping this section consistent with §2's stateless-first principle. The token SHOULD expire within a short window (this specification recommends 5 minutes) and MUST be rejected if presented after expiry or for a ceremony type other than the one it was issued for.

### 18.4 Relying Party Configuration

The Relying Party ID and allowed origin(s) MUST be explicit, implementation-controlled configuration, and MUST NOT be derived from a request's `Host` header or any other caller-supplied value — deriving either dynamically is one of the most common WebAuthn deployment mistakes, since a spoofed or misconfigured proxy `Host` header would otherwise influence which origins a credential is scoped to, undermining the entire binding WebAuthn is meant to provide.

Attestation conveyance SHOULD be `none` for this version — broadest authenticator compatibility, and avoids the vendor/privacy friction full attestation verification brings. Verifying a specific hardware vendor or model via attestation is out of scope for this version.

### 18.5 Enumeration Safety

The authentication-options endpoint (the first leg of the authentication ceremony, taking an email/identifier) MUST return an identical response shape whether or not that identifier corresponds to a real account with at least one registered credential — an empty allowed-credentials list and a real, single-use challenge token either way. This mirrors §6.2's tenant-discovery enumeration-safety requirement for the identical reason: a caller MUST NOT be able to distinguish "no such account" from "account exists but has no passkey" by response shape or timing.

### 18.6 Clone/Replay Detection

Each authenticator asserts a signature counter (`sign_count`) that MUST be non-decreasing across successful authentications. An implementation MUST reject an authentication whose presented counter is less than or equal to the credential's stored value, with one stated exception: many platform authenticators (e.g. built-in biometric unlock) always report a counter of `0` and never increment it — both stored and presented being `0` MUST NOT be treated as reuse, since neither carries any signal in that case. A counter that decreases from a previously-nonzero value, or repeats a previously-nonzero value, is treated as a possible cloned authenticator; an implementation SHOULD emit a distinct signal for this specific failure mode, separate from a generic failed-assertion event, since it is the one outcome here that suggests credential cloning rather than a simple wrong device or cancelled prompt.

### 18.7 Credential Lifecycle

An implementation SHOULD cap the number of credentials a single account may register (this specification does not mandate a specific number) and MUST reject registration beyond that cap with a clear error rather than accepting unbounded registrations. Removing an account's last remaining passkey MUST be permitted — this section's WebAuthn is strictly additive (§18.1), so a password or SSO login path always remains available as a fallback for every account able to register a passkey at all; an implementation offering a passwordless-only account model would need its own lockout-prevention rule, which this version does not define.

### 18.8 Interaction with SSO Enforcement and MFA

§6.3's `enforce_sso`/`allow_password_fallback` gate MUST apply to passkey login exactly as it applies to password login — a locally-registered passkey MUST NOT function as a way around an organization's SSO-required policy.

A successful passkey authentication SHOULD be treated as satisfying an organization's `mfa_required` login policy (§10) without requiring a separate TOTP/second-factor step — a WebAuthn ceremony is itself a possession factor, typically combined with a biometric or PIN verification at the authenticator, and requiring an additional factor on top is redundant friction rather than additional security. This mirrors how an SSO-authenticated login is already exempted from a local MFA requirement under this specification.

### 18.9 Non-Goals (This Section)

Deliberately out of scope for this version: step-up (re-)authentication for specific high-risk actions after an already-authenticated session exists, a passwordless-only account/signup model, magic-link or other non-WebAuthn passwordless mechanisms, and administrator-initiated passkey reset/recovery for a locked-out user (self-service registration/rename/removal of one's own credentials only).

## 19. Non-Goals (This Version)

- SAML connectors, including IdP-initiated SSO and certificate/metadata expiry monitoring for certificate-bearing connector types (`certificate_expires_at`, §4.1, is reserved but unused by `oidc`/`ldap`) — deferred to its own workstream given a materially different risk class (XML signature verification, well-known vulnerability classes like XXE and signature-wrapping attacks) that warrants a dedicated design document, threat model, and security review before implementation starts. See the companion RFC (`agf-profile/implementation/rfc-saml-connector.md`) for that design; it is a precondition for SAML work, not a substitute for the review itself.
- §17.5 and §18.9 list this version's dynamic-roles and passwordless-specific non-goals respectively, rather than repeating them here.

## 20. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-18 | Initial public working draft |
| 0.2.0 | 2026-07-18 | Added JIT provisioning (§9), login policies (§10), group→role mapping (§11, including the manual-override-safety requirement in §11.2 — a role sync must never silently revert an administrator's manual role promotion), and break-glass accounts (§12). §4 extended with role-source/idp-mapped-role/is-break-glass fields (§4.5) and the Role Mapping object (§4.6). §13 (renumbered from §9) narrowed to what remains deferred: SAML and its dependents (IdP-initiated SSO, certificate monitoring), directory sync, and session-scoped capabilities — SAML is intentionally out of scope for this version, reserved for a dedicated workstream given its distinct security-review requirements (XML signature verification, XXE, signature-wrapping attacks). |
| 0.3.0 | 2026-07-18 | Added the Group Membership Foundation (§13 — External Group Membership as the shared substrate every source converges on, a 5-state identity lifecycle, and an `identity.*` audit event taxonomy), SCIM provisioning (§14, a practical subset — not full RFC 7644 — with unsupported filter/PATCH expressions explicitly rejected rather than silently ignored; group PATCH writes to §13.1's membership record, never directly to a role), and Enterprise Directory Integration/LDAP (§15, read-only sync, explicitly not an authentication mechanism; renamed from "LDAP/Active Directory" since LDAP is the protocol and AD one deployment of it). §16 (renumbered from §13) narrowed further now that SCIM and LDAP are specified; SAML remains out of scope, now pointing to a dedicated companion RFC as its precondition-for-implementation gate. |
| 0.4.0 | 2026-07-18 | Added three new sections: Session Governance (§16 — an OPTIONAL live-session layer kept separate from the append-only Authentication Evidence record, covering a token-version revocation mechanism for invalidating an already-issued token before its natural expiry, and an OPTIONAL per-organization persistent-session object with atomic refresh-token rotation and whole-session reuse detection); Dynamic Roles and Permissions (§17 — a backward-compatible, OPTIONAL replacement for the fixed three-value role set used throughout §4.5/§4.6/§9/§11, built from a Permission/Role catalog that reproduces the pre-existing three-tier behavior exactly by default, plus organization-scoped custom roles as an additional OPTIONAL capability); and Passwordless Authentication/WebAuthn (§18 — an OPTIONAL, additive passkey first factor with its own credential object, enumeration-safety and Relying-Party-configuration requirements, and clone/replay detection for the WebAuthn signature counter). §4.1/§4.3/§4.5/§4.6 lightly amended to point at the new sections without changing any existing normative meaning; §2's "Stateless-first" principle clarified as an explicit, OPTIONAL opt-in rather than a reversal of the default. Old §16 (Non-Goals) renumbered to §19, its per-session-capability item removed (now specified in §16); old §17 (Change Log) renumbered to §20. |
