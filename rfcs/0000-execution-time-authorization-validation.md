# RFC 0000: Execution-Time Authorization Validation

- **Author(s):** Ramesh Kalimuthu
- **Affected spec(s):** new specification (Spec 30)
- **Status:** Draft
- **Discussion:** (none yet — draft)

## Summary

Defines an optional, separately-specified security control — Execution-Time Authorization
Validation — that a Policy Enforcement Point (PEP) MAY perform immediately before dispatching a
previously issued `ALLOW`/`ALLOW_WITH_CAUTION` Decision, to check whether the specific Authorities
that Decision relied on are still valid at the moment of dispatch. The check is deliberately narrow:
it re-verifies revocation state, expiry, and platform emergency-halt state only — not signatures,
chain structure, scope, or policy, none of which can change on an already-issued, already-verified
chain between decision time and dispatch time. This RFC fulfills the "future RFC" pointer explicitly
left open by RFC 0000-single-check-decision-semantics ("An implementation MAY perform execution-time
revalidation as a separate security control... This leaves room for a future RFC to define
execution-time authorization as an additional, separately-specified control").

## Motivation

RFC 0000-single-check-decision-semantics made normative, for the first time, that an authorization
decision is evaluated once, at issuance, and that dispatching an already-issued decision is not
itself a new authorization evaluation. That RFC deliberately stopped at documenting the resulting
gap rather than closing it: *"Implementations conforming to these semantics may therefore execute an
already-issued decision after the authority underlying that decision has subsequently become
ineffective, unless a separate execution-time control prevents dispatch."*

The `revocation-race-window` conformance example (`case-agf-synth-0001`,
`agf-standards/conformance/scenarios/revocation-race-window/`) is the concrete illustration: `ALLOW`
issued at `decided_at`; the specific Authority it relied on revoked one second later; the
already-issued decision dispatched and executed one more second after that; the runtime does not
observe the revocation until 31 seconds after dispatch. Under current semantics this is
correctly-behaving, not a bug — but "correctly-behaving" and "acceptable for a system whose stated
purpose is authorization enforcement" are not the same claim. For an agent-governance system whose
value proposition explicitly includes revocation and delegation attenuation, a decision that can
become stale before the action it authorized actually happens is a real security gap, not merely a
specification ambiguity.

This RFC does not propose closing that gap by re-running full decision evaluation at dispatch. Two
observations from the reference implementation make that both unnecessary and costly:

1. **Nothing about signature validity, chain structure, scope, or policy content can change between
   decision time and dispatch time** on an already-issued decision. The JWTs that were verified at
   decision time are immutable; re-verifying their ES256 signatures at dispatch time re-derives the
   same answer at real cost (one signature verification per chain hop) for zero new information.
2. **What genuinely can change in that window is exactly three things**: whether an Authority the
   decision relied on has since been revoked, whether an Authority has since expired, and whether the
   platform has since entered an emergency halt state. All three are cheap to check — a targeted
   per-Authority revocation lookup, a claim read, and a state flag read — none require redoing chain
   validation.

## Proposed change

### Scope: what this control checks, and what it deliberately does not

An implementation offering Execution-Time Authorization Validation performs, immediately before
dispatch of an already-issued Decision with `status` `ALLOW` (with or without the `caution`
qualifier):

1. **Platform state**: the deployment is not under an emergency halt (Spec 05 §8.4).
2. **Revocation**: none of the Decision's `authority_refs` (Spec 00 §3.4) has an Invalidation record
   (Spec 00 §3.6) with `cause` `revoked` or `superseded` whose `subject` is that Authority or an
   ancestor of it in its delegation lineage (Spec 05 §3's branch-cut model applies unchanged — a
   revoked ancestor invalidates the same descendants at execution time that it would at decision
   time).
3. **Expiry**: none of the Decision's `authority_refs` has passed its `expires_at` (Spec 00 §3.2).

This RFC explicitly does **not** require, and a conformant implementation MUST NOT require as part of
this control:

- Re-verification of any Authority's signature.
- Re-running chain structural validation (continuity, depth, cycle checks — Spec 02).
- Re-evaluating scope or policy (Spec 06).
- A fresh trust or risk score.

None of the above can have changed since decision time on the same, already-issued Decision; if an
implementation has a reason to believe they might have (e.g. a policy version was superseded), that
is grounds for a genuinely new authorization evaluation, not this control — this RFC's Execution-Time
Authorization Validation is a **freshness check on Authority validity**, not a second authorization
decision. This distinction matters for Spec 00 §7.1 and KERNEL-NEG-02: this control does not treat
the prior Decision as bearer authority for anything new, and it does not substitute for fresh
evaluation where fresh evaluation is actually required (e.g. a different Action). It can only narrow
what the original Decision already permitted; it can never broaden it.

### Outcome contract

| Result | Meaning | Consequence |
|---|---|---|
| `valid` | All three checks in §1-3 passed | Dispatch MAY proceed on the original Decision |
| `invalid` | Any one check failed | Dispatch MUST NOT proceed; the enforcement point MUST treat this as a `DENY` for the pending dispatch |

An `invalid` result MUST reference the specific pre-existing Invalidation record (Spec 00 §3.6) or
expiry condition that caused it — it does not fabricate a new Invalidation; revocation and expiry
are already-existing facts this control discovers, not events it causes. Where the failure was
revocation, the existing Invalidation record (created when the revocation itself was recorded) is
what gets referenced. This RFC proposes a new, non-kernel AGF artifact for recording that a check was
performed and what it found — an **Execution Validation Record** — specified in the accompanying
Spec 30 proposal, not as a kernel object (Spec 00's six objects are closed; see "Alternatives
considered"), but as a Core-format/Profile-layer artifact analogous to how the Execution Receipt
(Spec 07 §10) is an AGF serialization layered over the kernel Receipt object without redefining it.

### MUST / SHOULD / MAY allocation

- Implementing Execution-Time Authorization Validation at all is **OPTIONAL** for AGF conformance —
  consistent with RFC 0000-single-check-decision-semantics's "An implementation MAY perform
  execution-time revalidation."
- An implementation that advertises support for this control MUST perform all three checks in
  §1-3 for every dispatch it gates this way — partial implementation (e.g. checking revocation but
  not expiry) MUST NOT be described as conformant Execution-Time Authorization Validation.
- Whether *built-in* PEPs (e.g. a reference implementation's own protocol gateways) are REQUIRED to
  perform this check by default, versus it being opt-in configuration, is left to Unresolved
  Questions — this RFC does not mandate it.
- For a **portable Decision artifact** presented to a PEP outside the runtime that issued it (the
  general case this RFC and the `revocation-race-window` example describe), the issuing
  implementation SHOULD expose this control as a callable API operation (Spec 10 conventions) so
  that external PEPs have a standard way to perform it, since such a PEP cannot be reached by an
  internal code change the way a built-in gateway can.

## Backward compatibility

This is a new, optional artifact type and a new, optional API surface. No existing Decision, Receipt,
or Invalidation record's shape or meaning changes. An implementation that does not adopt this control
remains exactly as conformant as it was before this RFC, per RFC 0000-single-check-decision-semantics's
already-normative "MAY perform execution-time revalidation" — this RFC specifies what that MAY looks
like when exercised; it does not upgrade it to MUST.

If a reference implementation chooses to enable this control by default on its own built-in
enforcement points, that is a behavior change for that specific implementation (a decision that
previously always dispatched can now be denied at dispatch if revoked in the intervening window) —
that choice, and its compatibility handling, belongs to the implementation's own release process and
review, not to this specification-level RFC. See Unresolved Questions.

## Security considerations

### What this closes

Narrows, but does not eliminate, the window during which a stale decision can be acted on. Before
this control: the window is bounded only by however long a Decision remains dispatchable at all (in
the reference implementation's built-in gateways, effectively the same request; for a portable
Decision, potentially much longer). After this control, exercised by a PEP immediately before
dispatch: the window narrows to the interval between the validation check itself and the actual
dispatch call — which an implementation SHOULD make as small as possible (e.g. no unbounded work
between the two), but which this RFC does not specify a numeric bound for, since that bound is a
deployment/implementation property, not a protocol one.

### What this does not close

This control does not make revocation propagation instantaneous — it is bounded by whatever
revocation-lookup mechanism the PEP consults (Spec 05 §5.5's propagation targets for list-based
distribution; zero-latency by construction for a same-transaction store per Spec 28 §4.3). A
revocation recorded after the validation check but before dispatch completes is not caught by this
control — this is the same class of residual race any point-in-time check has, narrowed, not solved.
State this honestly rather than claim the gap is closed: it is narrowed from "the lifetime of a
Decision" to "the gap between one lookup and one dispatch call."

### Relationship to Spec 00 §7.1 / KERNEL-NEG-02

Spec 00 §7.1 establishes that a Decision or Receipt is evidence, not authority, and KERNEL-NEG-02
requires that a stored `ALLOW` MUST NOT be honored as bearer authority for a new request. This
control does not weaken that principle — it does not use the prior Decision as authority for
anything beyond what it already authorized, and it can only add a `DENY` outcome relative to the
original Decision, never add authorization the original Decision didn't already grant. An
implementation MUST NOT use this RFC's mechanism to re-authorize a *different* Action or Authority
set than the one the original Decision covered; that would be a new authorization evaluation, subject
to normal decision semantics, not this control.

### No new attack surface from the check itself

The revocation and expiry lookups this control performs are read-only, targeted, and already exist as
mechanisms in Spec 05 (revocation) and the kernel Authority object (expiry) — this RFC composes
existing checks at a new point in the request lifecycle; it does not introduce new cryptographic
material, new trust anchors, or new write paths.

## Alternatives considered

**Full re-evaluation at dispatch (a second `perform_decision()`-equivalent call).** Rejected: pays
full chain signature verification and policy re-evaluation cost for information that provably cannot
have changed (signatures, structure, scope, policy content are immutable once the chain was issued
and verified once). This is the option RFC 0000-single-check-decision-semantics's own "Alternatives
considered" section flagged and deferred, not endorsed, as "a much larger change with its own
performance and latency tradeoffs."

**Adding Execution-Time Authorization Validation as a seventh kernel object (amending Spec 00).**
Rejected: Spec 00 §1 defines exactly six kernel objects and states everything else "MUST NOT redefine
[the kernel]." This control is optional (see MUST/SHOULD/MAY allocation above), which is inconsistent
with kernel status — the six kernel objects are things "every conformant implementation MUST
support." Modeling it instead as a Core-format/Profile-layer artifact that references, but does not
extend, the existing kernel Decision and Invalidation objects keeps the kernel closed while still
giving the control a normative shape.

**Doing nothing (leaving the gap as RFC 0000-single-check-decision-semantics documented it).**
Rejected: that RFC explicitly reserved this as future work rather than a closed question, and the
gap it documents is a real, not hypothetical, security limitation for a system whose stated purpose
includes revocation enforcement.

## Unresolved questions

**Built-in gateway default.** Whether a reference implementation's own built-in protocol gateways
(HTTP, MCP, A2A adapters, Specs 21-23) should perform this check by default, as opt-in configuration,
or not at all, is left open. Verified against current source, the built-in gateways already call
decision and dispatch back-to-back in the same request (`agf-runtime`, ~50-56 lines apart) — the
marginal benefit there is narrowing an already-small window at the cost of a few indexed lookups per
dispatch, which is a deployment tradeoff this RFC does not resolve.

**External PEP requirement level.** Whether a PEP consuming a portable Decision artifact SHOULD or
MUST perform this check before dispatch — this RFC currently proposes SHOULD (see Proposed change),
but maintainers may judge the security posture warrants MUST for any PEP claiming AGF conformance.

**Numeric latency guidance.** Whether Spec 30 should recommend a maximum interval between the
validation check and the actual dispatch call (analogous to Spec 05 §5.5's propagation targets), or
leave it fully implementation-defined.

**Execution Validation Record retention and query surface.** Whether this new artifact needs its own
audit/query API (analogous to Spec 10 §5.6's Receipt endpoints) in the initial version of Spec 30, or
whether that can follow once a reference implementation exists — this RFC leans toward including a
minimal query surface from the start (consistent with Receipt), but leaves the exact shape to the
Spec 30 proposal itself.
