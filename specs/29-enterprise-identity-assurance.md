# Specification 29: Enterprise Identity Assurance

**Version:** 0.3.0 (Draft)
**Status:** Working Draft — §4-15 (the identity-provider/binding/evidence data model, tenant discovery, domain verification, the Identity Assurance annotation, JIT provisioning, login policies, group→role mapping, break-glass accounts, the group-membership/lifecycle/audit foundation, SCIM provisioning, and Enterprise Directory Integration/LDAP) has a reference implementation. SAML, IdP-initiated SSO, certificate monitoring, and session management (§16) are out of scope for this version — SAML has a dedicated companion RFC as its own precondition-for-implementation gate.
**Supersedes:** None — new profile
**Layer:** Profile

## 1. Introduction

AAP-Core (Spec 00) defines **Actor** as "the human, service, or agent instance that acts," and its Decision object records policy version, trust score, and reasoning — but nothing about *how* a human actor authenticated before initiating the delegation that led to a decision. Spec 08 (Identity Registry) resolves *agent* identity — DIDs and their key material, the chain-of-custody concern for delegated authority once it exists. Neither spec addresses the step before that: verifying the human who is about to create or exercise authority, and carrying evidence of that verification into the eventual decision record.

This specification closes that gap for enterprise deployments: human authentication via an external, organization-managed Identity Provider (IdP) — OIDC in this version — and a compact, privacy-preserving annotation of that authentication carried into the signed decision artifact (Spec 07). It does not modify AAP-Core's six objects or their correlation rules; it defines an OPTIONAL enrichment of the existing Decision object's context, plus the supporting identity-provider/binding/evidence model that produces it.

## 2. Guiding Principles

**Authentication ≠ Authorization.** The IdP proves who authenticated. AGF decides what that identity may do. An implementation MUST NOT conflate the two — this specification defines only how authentication evidence is recorded and referenced, never how it factors into a policy decision (that remains entirely Spec 06's concern; §7.4 makes explicit that an identity-assurance lookup failure MUST NOT change the decision outcome).

**Federation, not migration.** An implementation MUST NOT store enterprise passwords. Identity remains at the IdP; this specification's data model stores only a trusted reference to it (§4.2) and evidence that a verification event occurred (§4.3), never the credential itself.

**Stateless-first.** This version deliberately does not introduce a server-side session object. An implementation MAY continue to use whatever stateless bearer-token model it already has (e.g. Spec 01's delegation tokens, or an analogous short-lived access/refresh token pair for human actors) unmodified. §4.3's Authentication Evidence record is written once, at authentication time, and is never read or re-checked during authorization — it is audit evidence, not a live session gate. §16 discusses why session-scoped capabilities (remote logout, active-session listing) are deliberately deferred rather than folded into this version.

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
| `default_role` | string | Yes | `owner` \| `admin` \| `viewer`, default `viewer`. The role a JIT-provisioned account receives absent a group-mapping match (§9, §11). |
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

No `session_id`, no revocation field. Deleting or invalidating a live session, if an implementation has one at all, is entirely orthogonal to this record — the record documents that authentication happened; whether a subsequent bearer token derived from it is still valid is a separate concern this specification does not govern (§2).

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
| `role` | string | Yes | The *effective* role — unchanged in meaning from before this specification. Every existing reader of this field (authorization checks, token claims) continues to work unmodified. |
| `role_source` | string | Yes | `manual` \| `idp`. Default `manual`. Governs whether §11's sync is allowed to overwrite `role` on login. |
| `idp_mapped_role` | string \| null | No | The most recent value §11's mapping computed, independent of `role_source`. Audit/troubleshooting visibility only — never itself the effective role. |

### 4.6 Role Mapping

A rule translating an IdP-asserted group or claim into an AGF role.

| Field | Type | Required | Description |
|-------|------|----------|--------------|
| `id` | string | Yes | |
| `provider_id` | string | Yes | The Identity Provider (§4.1) this rule applies to. |
| `match_type` | string | Yes | `group` \| `claim`. |
| `match_key` | string | Yes | The claim name to inspect — default `groups` for `match_type: group`. |
| `match_value` | string | Yes | For `match_type: group`, a value that MUST appear in the named claim's list. For `match_type: claim`, a value the named claim's (stringified) scalar MUST equal. |
| `role` | string | Yes | `owner` \| `admin` \| `viewer`. |
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

## 16. Non-Goals (This Version)

- SAML connectors, including IdP-initiated SSO and certificate/metadata expiry monitoring for certificate-bearing connector types (`certificate_expires_at`, §4.1, is reserved but unused by `oidc`/`ldap`) — deferred to its own workstream given a materially different risk class (XML signature verification, well-known vulnerability classes like XXE and signature-wrapping attacks) that warrants a dedicated design document, threat model, and security review before implementation starts. See the companion RFC (`agf-profile/implementation/rfc-saml-connector.md`) for that design; it is a precondition for SAML work, not a substitute for the review itself.
- Any per-session capability — active-session listing, remote logout, continuous access evaluation. §2 explains why session-scoped capabilities are deliberately not this version's problem: they require a genuinely different, persistent-session architecture that this specification does not assume every implementation has, and forcing that assumption would have made every other section of this specification a prerequisite for a session feature most deployments do not need on day one. A future specification MAY define that architecture without requiring changes to §4-15 of this one.

## 17. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-18 | Initial public working draft |
| 0.2.0 | 2026-07-18 | Added JIT provisioning (§9), login policies (§10), group→role mapping (§11, including the manual-override-safety requirement in §11.2 — a role sync must never silently revert an administrator's manual role promotion), and break-glass accounts (§12). §4 extended with role-source/idp-mapped-role/is-break-glass fields (§4.5) and the Role Mapping object (§4.6). §13 (renumbered from §9) narrowed to what remains deferred: SAML and its dependents (IdP-initiated SSO, certificate monitoring), directory sync, and session-scoped capabilities — SAML is intentionally out of scope for this version, reserved for a dedicated workstream given its distinct security-review requirements (XML signature verification, XXE, signature-wrapping attacks). |
| 0.3.0 | 2026-07-18 | Added the Group Membership Foundation (§13 — External Group Membership as the shared substrate every source converges on, a 5-state identity lifecycle, and an `identity.*` audit event taxonomy), SCIM provisioning (§14, a practical subset — not full RFC 7644 — with unsupported filter/PATCH expressions explicitly rejected rather than silently ignored; group PATCH writes to §13.1's membership record, never directly to a role), and Enterprise Directory Integration/LDAP (§15, read-only sync, explicitly not an authentication mechanism; renamed from "LDAP/Active Directory" since LDAP is the protocol and AD one deployment of it). §16 (renumbered from §13) narrowed further now that SCIM and LDAP are specified; SAML remains out of scope, now pointing to a dedicated companion RFC as its precondition-for-implementation gate. |
