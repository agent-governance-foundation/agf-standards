# RFC 0000: Single-Check Decision Semantics

- **Author(s):** Ramesh Kalimuthu
- **Affected spec(s):** Spec 05 §5.5 (Bounded Propagation Guarantees)
- **Status:** Draft
- **Discussion:** (none yet — draft)

## Summary

Makes normative, for the first time, the lifecycle of an authorization decision: an authorization decision is evaluated once, at the moment it is issued. Subsequent presentation or dispatch of that already-issued decision does not itself constitute a new authorization evaluation. Spec 05 §5.5's propagation-window `DENY` rule governs a *new* decision evaluation occurring during or after the propagation window — it does not govern dispatch of a decision issued before the window began. This is a documentation change, not a behavior change, but it documents a security-relevant limitation: implementations conforming to these semantics may execute an already-issued decision after the authority underlying it has become ineffective, unless a separate execution-time control prevents dispatch.

## Motivation

Spec 05 §5.5 describes what happens when "an agent acts during the propagation window," and mandates `DENY` in that case. Nothing in the specs currently distinguishes that rule — which governs a *new* authorization evaluation happening during the window — from the separate case of an *already-issued* decision being dispatched or executed after the window has begun. Without that distinction, a reader can reasonably interpret §5.5 as requiring that any action taken during the propagation window must be denied, including dispatch of a decision that was correctly issued *before* the window opened. That reading is wrong, but the specs currently give no way to know that.

This ambiguity is not hypothetical. The `revocation-race-window` conformance example (`case-agf-synth-0001`, `agf-standards/conformance/scenarios/revocation-race-window/`) illustrates it directly: a decision is correctly evaluated and issued as `ALLOW` at `decided_at`; the underlying authority is revoked one second later; the gateway dispatches the already-issued decision one second after that, without a second authorization evaluation; the runtime does not observe the revocation until 31 seconds after dispatch. An external review of that example (v0_2 review, private) flagged the dispatch step as an apparent §5.5 violation — a plausible reading given the specs' current silence, and exactly the ambiguity this RFC resolves. That example is used here as an illustration of the ambiguity in practice, not as the justification for the change itself: the underlying issue — decision-lifecycle semantics are undocumented — exists independently of that one example, and would eventually surface in any implementation drawing the same reasonable-but-wrong conclusion from §5.5's current text.

## Proposed change

### Decision lifecycle

```
New /v1/decide evaluation
        ↓
authority validation
        ↓
decision issued
        ↓
later dispatch
        ↓
NO new authorization decision
```

### Single decision evaluation

This RFC scopes itself narrowly to one authorization evaluation per issued decision — distinct from implementation-level concerns (HTTP retries, idempotency, internal function calls, logging) that are not addressed here and that implementations remain free to handle however they choose:

> For an authorization decision, authority validation is performed as part of the decision evaluation that produces the issued decision. Subsequent dispatch or execution of that already-issued decision does not itself constitute a new authorization evaluation.

The consequence that follows directly from this:

> Revocation occurring after the decision has been issued does not retroactively change that issued decision. It may affect a later, independently evaluated authorization request.

This RFC does not add an implementation-level normative statement such as "AGF MUST perform exactly one call to the authorization validator" — that would unnecessarily constrain implementation architecture (caching, retries, internal policy composition) that this RFC has no opinion on. The normative content stays at the level of the authorization-decision lifecycle, not call counts.

### Already-issued decision dispatch

The conceptual core of this RFC is the distinction between decision-time and execution-time authority:

> Decision-time authorization is not execution-time authorization. A decision records the authorization determination made at decision time. Under the current decision semantics, dispatching that decision does not independently establish that the underlying authority remains effective at execution time.

**Current semantics:**

> An already-issued authorization decision MUST NOT be treated as undergoing a new authorization evaluation merely because it is subsequently dispatched or executed. Spec 05 §5.5 applies when a new authorization decision is evaluated during or after the propagation window.

**Future feature** (a separate statement, not a caveat on the one above):

> An implementation MAY perform execution-time revalidation as a separate security control. Such revalidation is not part of the original decision evaluation and requires its own defined semantics.

The phrase "MUST NOT be treated as undergoing" is deliberate — a claim about decision semantics, not implementation architecture. This RFC does not say "MUST NOT re-check," because that would prescribe how implementations describe or structure their own internal calls, which is not this RFC's concern.

### Relationship to §5.5 propagation-window rule

§5.5's existing table and `DENY` rule are unchanged by this RFC. What changes is scope: §5.5 applies when a *new* authorization decision is evaluated during or after the propagation window. It does not apply to dispatch of a decision issued before the window opened — that case is governed by the "Already-issued decision dispatch" semantics above, not by §5.5.

### Explicit exclusion of `X-AGF-Test-Force-Execute`

The reference implementation (`agf-runtime`) has a test-only header, `X-AGF-Test-Force-Execute`, that forwards a call upstream despite a blocking decision, for exercising `EXECUTED_AFTER_DENY` / `EXECUTED_WITHOUT_APPROVAL` violations end-to-end in conformance testing. It is structurally disabled outside non-production environments. This RFC's semantics describe production decision/dispatch behavior; this test hook is out of scope and must not be read as contradicting or qualifying it.

### Built-in gateway routes vs. a portable decision artifact

This RFC's "already-issued decision, later dispatch" lifecycle should not be read as a claim about what `agf-runtime`'s own built-in gateway routes currently do internally. Verified against current source (`agf-runtime/src/presentation/api/routes/http_gateway_proxy.py`, `mcp_gateway_proxy.py`, `a2a_gateway_proxy.py`): each of the three built-in gateway-proxy routes calls `perform_decision()` synchronously, in the same request, immediately before dispatching to the upstream target — the caller presents a raw delegation chain (`X-AGF-Chain`), not a previously-issued decision reference, and there is no path in the current reference implementation where a caller presents an already-issued decision for later dispatch without a fresh evaluation.

The built-in HTTP, MCP, and A2A gateway routes currently perform their decision evaluation as part of the dispatch request itself. This RFC does not characterize those routes as an implementation of a separate already-issued-decision dispatch path. The normative lifecycle instead defines the semantics of an issued decision as a portable authorization artifact that may subsequently be presented to a PEP, including PEPs outside these built-in gateway routes — exactly the shape of the `revocation-race-window` conformance example, where `execution_receipt.signer` (`gateway-01`) is a PEP acting on a previously issued decision, illustrating the general protocol contract this RFC defines rather than a specific `agf-runtime` code path.

### Future execution-time revalidation is not prohibited

> This RFC does not prohibit a future implementation from adding execution-time revalidation as a separate security feature; it defines that such revalidation is not part of the current decision semantics.

This leaves room for a future RFC to define execution-time authorization as an additional, separately-specified control, rather than foreclosing it.

## Backward compatibility

No behavior change — this RFC describes existing `agf-runtime` behavior (verified above) and existing conformance-example narrative, not a proposed change to it.

It is still a normative addition to Spec 05 §5.5's text, so it still carries a version-impact recommendation per `GOVERNANCE.md`: a Minor version increment, subject to the specification version current at the time the accepted RFC is incorporated (not hardcoded here, since Spec 05 currently sits at 0.3.0 (Draft) and this RFC may or may not be incorporated in the same PR as RFC 0000-revocation-authorization, which also targets Spec 05).

## Security considerations

This RFC does not close the interval between decision-time authority and execution-time authority. It makes that limitation normative and explicit. Implementations conforming to these semantics may therefore execute an already-issued decision after the authority underlying that decision has subsequently become ineffective, unless a separate execution-time control prevents dispatch.

This RFC does not preclude a future specification defining execution-time revalidation or another execution authorization mechanism.

This is not merely a documentation change in security terms: it documents a security-relevant limitation that previously existed only as unstated, verified runtime behavior. No new attack surface is introduced by documenting it — the underlying gap is pre-existing and unchanged by this RFC.

## Alternatives considered

**Requiring re-validation at dispatch** (i.e., changing runtime behavior instead of documenting it): rejected here as a much larger change with its own performance and latency tradeoffs, out of scope for a documentation-focused RFC. Could be proposed separately as a future RFC defining an execution-time revalidation control (see "Future feature," above).

**Doing nothing** (leaving §5.5 as currently written): rejected — the ambiguity is real, already caused one external review to flag a correctly-behaving conformance example as an apparent spec violation, and will recur for any other implementer or reviewer reasoning from §5.5's text alone.

## Unresolved questions

None at the normative-content level; this RFC is a scoping/clarification of existing text and verified existing behavior. Open only in the sense that maintainers may prefer a different section placement within §5.5, or a different exact wording for the "Current semantics" / "Future feature" statements above.
