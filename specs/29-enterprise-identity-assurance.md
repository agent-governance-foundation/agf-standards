# Specification 29: Enterprise Identity Assurance

**Version:** 0.1.0 (Draft)
**Status:** Working Draft — §4-7 (the identity-provider/binding/evidence data model, tenant discovery, domain verification, and the Identity Assurance annotation on decision artifacts) has a reference implementation. SAML/LDAP/SCIM connectors, JIT provisioning without invite, login policies, and session management (§9) are out of scope for this version.
**Supersedes:** None — new profile
**Layer:** Profile

## 1. Introduction

AAP-Core (Spec 00) defines **Actor** as "the human, service, or agent instance that acts," and its Decision object records policy version, trust score, and reasoning — but nothing about *how* a human actor authenticated before initiating the delegation that led to a decision. Spec 08 (Identity Registry) resolves *agent* identity — DIDs and their key material, the chain-of-custody concern for delegated authority once it exists. Neither spec addresses the step before that: verifying the human who is about to create or exercise authority, and carrying evidence of that verification into the eventual decision record.

This specification closes that gap for enterprise deployments: human authentication via an external, organization-managed Identity Provider (IdP) — OIDC in this version — and a compact, privacy-preserving annotation of that authentication carried into the signed decision artifact (Spec 07). It does not modify AAP-Core's six objects or their correlation rules; it defines an OPTIONAL enrichment of the existing Decision object's context, plus the supporting identity-provider/binding/evidence model that produces it.

## 2. Guiding Principles

**Authentication ≠ Authorization.** The IdP proves who authenticated. AGF decides what that identity may do. An implementation MUST NOT conflate the two — this specification defines only how authentication evidence is recorded and referenced, never how it factors into a policy decision (that remains entirely Spec 06's concern; §7.4 makes explicit that an identity-assurance lookup failure MUST NOT change the decision outcome).

**Federation, not migration.** An implementation MUST NOT store enterprise passwords. Identity remains at the IdP; this specification's data model stores only a trusted reference to it (§4.2) and evidence that a verification event occurred (§4.3), never the credential itself.

**Stateless-first.** This version deliberately does not introduce a server-side session object. An implementation MAY continue to use whatever stateless bearer-token model it already has (e.g. Spec 01's delegation tokens, or an analogous short-lived access/refresh token pair for human actors) unmodified. §4.3's Authentication Evidence record is written once, at authentication time, and is never read or re-checked during authorization — it is audit evidence, not a live session gate. §9 discusses why session-scoped capabilities (remote logout, active-session listing) are deliberately deferred rather than folded into this version.

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
| `connector_type` | string | Yes | `oidc` in this version. `saml`, `ldap`, `scim` are reserved values an implementation MAY accept in storage for forward compatibility but MUST reject at connection time with a clear "not yet supported" error rather than silently no-op. |
| `connector_config` | object | Yes | Non-secret connector configuration. For `oidc`: `issuer`, `client_id`, `redirect_uri` are REQUIRED. |
| `display_name` | string | Yes | Shown to the user during tenant discovery (§6). |
| `is_default` | boolean | Yes | When an organization has more than one active provider, tenant discovery (§6) resolves to the default. |
| `enforce_sso` | boolean | Yes | When true, combined with `allow_password_fallback: false`, password-based authentication MUST be rejected for this organization (§6.3). |
| `allow_password_fallback` | boolean | Yes | Default true. The safety valve against a misconfigured `enforce_sso` locking out every admin (§6.3). |
| `status` | string | Yes | `active` \| `disabled`. |
| `certificate_expires_at` | string (ISO 8601) | No | Reserved for certificate-bearing connector types (SAML); unused by `oidc`. |

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

Independently, an implementation MUST always preserve some non-SSO recovery path for at least one privileged account per organization (a "break glass" mechanism), regardless of `enforce_sso` — a misconfigured provider (wrong issuer, revoked client credentials at the IdP) MUST NOT be able to permanently lock an organization out of its own AGF account. This version treats `allow_password_fallback` as the interim safety valve (default `true`); a dedicated break-glass account flow is deferred to a later version (§9).

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

## 9. Non-Goals (This Version)

- SAML, LDAP, and SCIM connectors — `connector_type` reserves the values (§4.1) but no behavior is specified for them in this version.
- JIT provisioning without a prior invitation — this version requires an implementation to gate first-time binding creation (§4.2) on an existing, unexpired invitation mechanism the implementation already has for adding members to an organization; provisioning a new account from IdP claims alone is out of scope.
- Login policies (IP/country/device/risk-based restrictions).
- A dedicated break-glass account flow — §6.3 describes the interim safety valve this version relies on instead.
- Certificate/metadata expiry monitoring for certificate-bearing connector types.
- Directory sync, group-to-role mapping beyond whatever static role model the implementation already has, and any per-session capability — active-session listing, remote logout, continuous access evaluation. §2 explains why session-scoped capabilities are deliberately not this version's problem: they require a genuinely different, persistent-session architecture that this specification does not assume every implementation has, and forcing that assumption would have made every other section of this specification a prerequisite for a session feature most deployments do not need on day one. A future specification MAY define that architecture without requiring changes to §4-8 of this one.

## 10. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-18 | Initial public working draft |
