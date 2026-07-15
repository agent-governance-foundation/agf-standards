# Specification 01: Delegation Token Format

**Version:** 0.1.1 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.0  
**Layer:** Core format  

## 1. Introduction

A delegation token is a signed cryptographic statement that grants authority from an issuer to a subject. This specification defines the format, encoding, and validation rules for delegation tokens in the Agent Governance ecosystem.

## 2. Format

### 2.1 Encoding

Delegation tokens MUST be encoded as JSON Web Tokens (JWT) as defined in RFC 7519.

### 2.2 Header

The JWT header MUST contain:

```json
{
  "alg": "ES256",
  "typ": "JWT",
  "kid": "string"
}
```

| Claim | Required | Description |
|-------|----------|-------------|
| `alg` | Yes | Signature algorithm. MUST be `ES256` (ECDSA with P-256 and SHA-256) |
| `typ` | Yes | Token type. MUST be `"JWT"` |
| `kid` | Yes | Key ID to identify the verification key |

### 2.3 Payload — Required Claims

```json
{
  "iss": "did:agf:acme:alice",
  "sub": "did:agf:acme:agent:builder",
  "aud": "https://verifier.example.com",
  "exp": 1735689600,
  "iat": 1735603200,
  "jti": "del_abc123",
  "scope": ["read:calendar", "write:draft"]
}
```

| Claim | Type | Required | Description |
|-------|------|----------|-------------|
| `iss` | string | Yes | Issuer identifier (DID format: `did:agf:{namespace}:{id}`) |
| `sub` | string | Yes | Subject identifier (DID format) |
| `aud` | string or `[]string` | Yes | Audience(s) — verifiers intended to accept this token |
| `exp` | number | Yes | Expiration time (Unix timestamp, seconds) |
| `iat` | number | Yes | Issued at time (Unix timestamp, seconds) |
| `jti` | string | Yes | Unique delegation ID (max 64 chars, alphanumeric + underscore) |
| `scope` | array of strings | Yes | Permissions being delegated |

### 2.4 Payload — Optional Claims

```json
{
  "parent": "del_parent123",
  "max_depth": 5,
  "policy_version": "acme/policies/payroll/approve@1.2.0",
  "constraints": {
    "time_of_day": ["09:00-17:00"],
    "location": "office"
  }
}
```

| Claim | Type | Description |
|-------|------|-------------|
| `parent` | string | Parent delegation ID (for chain linking) |
| `max_depth` | number | Maximum allowed sub-delegation depth (default: 5) |
| `policy_version` | string | Policy version to evaluate this delegation under (if omitted, the PDP resolves the org's active policy). If present but not loadable, the PDP surfaces the mismatch and caps the decision at `ALLOW_WITH_CAUTION` — see Spec 06 §6.5 |
| `constraints` | object | Additional constraints (time, location, etc.) |

### 2.5 Scope Format

Scopes MUST follow this pattern:

```
{action}:{resource_type}[/{resource_path}]
```

**Actions (predefined):**

| Action | Description |
|--------|-------------|
| `read` | Read data from resource |
| `write` | Write/modify data |
| `create` | Create new resources |
| `delete` | Delete resources |
| `approve` | Approve workflows |
| `delegate` | Delegate authority to others |
| `execute` | Execute operations |

**Resource types (examples):**

```
calendar, document, payment, build, deployment, ticket, user, role, policy
```

**Examples:**

```
read:calendar
write:document/team/shared
approve:payment/amount<10000
delegate:role/admin
```

### 2.6 DID Format

DIDs MUST use the Agent Governance Foundation method:

```
did:agf:{namespace}:{specific-id}
```

**Components:**

| Component | Description | Example |
|-----------|-------------|---------|
| `namespace` | Organization or domain identifier | `acme`, `example`, `gov.uk` |
| `specific-id` | Unique identifier within namespace | `agent:build-server-01`, `alice`, `service:payroll` |

**Examples:**

```
did:agf:acme:alice
did:agf:acme:agent:build-server-01
did:agf:acme:service:payroll
did:agf:example:demo-agent
```

Future versions will support additional standard DID methods (`did:key`, `did:web`, `did:indy`) alongside `did:agf`.

### 2.7 Scope Canonicalization

To ensure consistent comparison, all scopes MUST be canonicalized before validation.

**Rules:**

1. **Case:** All scopes are case-sensitive (keep original case)
2. **Path normalization:**
   - Remove trailing slashes: `read:calendar/` → `read:calendar`
   - Collapse multiple slashes: `write:document//team///shared` → `write:document/team/shared`
   - Resolve `.` and `..` paths: `read:calendar/./personal/../shared` → `read:calendar/shared`
3. **Parameter normalization:**
   - Remove whitespace around operators: `amount < 10000` → `amount<10000`
   - Operators `<`, `<=`, `>`, `>=`, `=` are preserved as-is
   - Numeric values are preserved as strings (no type casting)

**Scope equality:**

Two scopes are equal if their canonicalized forms are identical string matches.

**Example:**

```
Token A scope: "write:document/team//shared"
Token B scope: "write:document/team/shared/"

Canonicalized A: "write:document/team/shared"
Canonicalized B: "write:document/team/shared"
Result: Equal ✓
```

Canonicalization MUST be applied before any scope comparison or intersection operation (see Spec 02 §3.5).

## 3. Validation Rules

### 3.1 Signature Validation

The token's signature MUST be verified using the public key identified by `kid` in the header. If the key cannot be found or the signature is invalid, the token MUST be rejected.

### 3.2 Expiration

If `exp < current time` (allow 5-second clock skew), the token MUST be rejected as expired.

### 3.3 Audience

If the verifier's identifier is not present in `aud`, the token MUST be rejected.

**Wildcard audiences are not supported.** A literal `aud: "*"` is treated as a normal audience value and will fail verification unless the verifier's identifier is literally `"*"`. This is a deliberate safety decision — an implicit wildcard-match exception is a common source of overly permissive token acceptance — not an oversight. Issuers MUST list every intended verifier explicitly in `aud`.

### 3.4 Issued At

If `iat > current time + 60 seconds`, the token MUST be rejected (future-dated tokens are not allowed).

### 3.5 Token Lifetime

If `exp - iat` exceeds `max_token_lifetime` (default: 90 days, see §5.4), the token MUST be rejected with `LIFETIME_EXCEEDED`. This is enforced at two points:

1. **Issuance** — the token builder refuses to issue a token whose requested lifetime exceeds the maximum.
2. **Verification** — the verifier independently re-checks `exp - iat` on every token in a chain, so a token issued before this rule existed (or by a non-conformant issuer) is still rejected at validation time.

## 4. Example Token

### 4.1 Creation

```python
import jwt
from datetime import datetime, timedelta

payload = {
    "iss": "did:agf:acme:alice",
    "sub": "did:agf:acme:agent:builder",
    "aud": "https://build.acme.com",
    "exp": datetime.now() + timedelta(hours=1),
    "iat": datetime.now(),
    "jti": "del_7f3e9a2b",
    "scope": ["read:source-code", "run:build"],
    "max_depth": 3
}

token = jwt.encode(payload, private_key, algorithm="ES256")
```

### 4.2 Verification

The verifier resolves the signing key via the `kid` claimed in the JWT header (falling back to a `kid` derived from `iss` if the header omits it — see Spec 08/09 for key resolution), then decodes with the full required-claims list and clock-skew leeway:

```python
try:
    payload = jwt.decode(
        token,
        public_key,          # resolved via kid (header, or derived from iss)
        algorithms=["ES256"],
        audience="https://build.acme.com",
        options={
            "require": ["exp", "iat", "iss", "sub", "jti"],
            "leeway": 5,      # §3.4/§5.4 clock skew
        },
    )
except jwt.ExpiredSignatureError:
    # Token expired (§3.2)
except jwt.InvalidAudienceError:
    # Wrong audience (§3.3) — note: "*" is not a wildcard, see §3.3
```

After decode, the verifier separately checks `iat` is not more than 60 seconds in the future (§3.4) and that `exp - iat` does not exceed the 90-day maximum (§3.5) — neither of these is expressible via PyJWT's built-in `options`, so they run as explicit post-decode checks.

## 5. Security Considerations

### 5.1 Key Size

ES256 uses P-256 curve with 256-bit keys. Minimum key size: 256 bits.

### 5.2 Token Lifetime

Tokens SHOULD have short lifetimes (minutes to hours, not days). Long-lived tokens increase risk.

### 5.3 jti Uniqueness

The `jti` MUST be globally unique within the issuer's domain. Use UUID or `{prefix}_{timestamp}_{random}`.

### 5.4 Clock Skew

Verifiers SHOULD allow up to 5 seconds of clock skew when checking `exp` and `iat`.

**NTP-synchronized environments:** The 5-second default is appropriate for servers and cloud workloads where NTP synchronization is reliable.

**IoT and edge environments:** Devices without reliable NTP access may have significant clock drift. Implementers in these environments SHOULD:

1. Use a wider tolerance (up to 60 seconds) if NTP synchronization cannot be guaranteed
2. Prefer relative time validation: verify that `exp - iat` is within the declared lifetime, and track locally elapsed time since the token was first used rather than comparing absolute timestamps
3. Treat tokens from IoT/edge issuers as Local Zone trust (see Spec 03 §2.1); actions requiring Domain Zone confidence require domain connectivity and a fresh validation
4. Document the maximum tolerated clock drift in the conformance certificate

**Hard limit:** Regardless of environment, verifiers MUST NOT accept tokens where `exp - iat` exceeds `max_token_lifetime` (default: 90 days). This prevents indefinitely-valid tokens from being issued with manipulated timestamps. See §3.5 for the enforcement points.

## 6. References

- RFC 7519 — JSON Web Token (JWT)
- RFC 7518 — JSON Web Algorithms (JWA)
- RFC 7517 — JSON Web Key (JWK)
- NIST SP 800-56A — ECDSA recommendation

## 7. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
| 0.1.1 | 2026-07-14 | §2.4 `policy_version` claim description corrected (PDP resolves the org's active policy, not "latest") and cross-referenced to Spec 06 §6.5 mismatch surfacing |
