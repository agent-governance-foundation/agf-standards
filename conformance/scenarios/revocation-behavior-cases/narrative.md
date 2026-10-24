# Revocation behavior cases (non-runnable)

These proposed cases translate existing draft requirements into reviewable
conformance scenarios. They are **not runnable fixtures** and do not establish
that any implementation passes. The published conformance harness is not yet
available; see the [conformance status](../../README.md#status).

The cases use fictional agents and authority identifiers. They do not change
normative specification text.

## R1 — Branch cut preserves an independent branch

**Specification basis:** Spec 05 v0.3.0, §§3.2–3.3; Spec 11 v0.5.0,
REVOKE-03 and REVOKE-04.

**Initial state:** Grantor A issues authority to agents B and D. B delegates a
child authority to C. The B and D branches are independent; no authority in
D's lineage descends from B's grant.

**Action:** Revoke A→B, then evaluate B's authority, C's delegated authority,
and D's authority against the same revocation state.

**Expected result:** B's authority and descendant C's authority are invalid.
D's independent authority remains valid. A result that invalidates D because
it shares the same grantor fails this case.

## R2 — Revocation is checked on an applicable execution path

**Specification basis:** Spec 30 v0.3.0, §§3.2, 3.5, and 6; Spec 05 v0.3.0,
§3.3.

**Applicability:** Exercise the approved-execution path for a `REVIEW_REQUIRED`
Decision, on which Spec 30 §6 requires execution-time validation. A test of a
general `ALLOW` dispatch is applicable only when the implementation explicitly
enables that check; §6 leaves built-in PEP behavior for that path to the
implementation.

**Initial state:** A Decision refers to an authority that is valid when the
Decision is issued. The required human approval is recorded. Before dispatch,
an ancestor authority is revoked and its Invalidation record is visible to
the execution-time validator.

**Action:** Submit the approved execution for validation immediately before
dispatch.

**Expected result:** Validation returns `invalid` with reason
`authority_revoked` and references the applicable Invalidation record(s). The
PEP does not dispatch the upstream action. A test must not infer this outcome
for a general `ALLOW` path unless execution-time validation is enabled there.

## R3 — Concurrent parent and child revocations are both retained

**Specification basis:** Spec 05 v0.3.0, §§3.3, 4.4, and 8.5.

**Initial state:** Parent authority P has descendant authority C. The
revocation store contains neither revocation. Two writers can update the same
store concurrently.

**Action:** Start revocation of P and revocation of C concurrently, synchronize
the writers so their writes overlap, then read the final revocation state and
validate C. Repeat with reversed scheduling where the test harness allows it.

**Expected result:** Both revocation records remain present. C is invalid via
its own revocation and via P's branch cut. The final authority result is the
same regardless of write completion order. If version counters use
compare-and-swap, a failed compare-and-swap is retried against the latest
version rather than overwriting another writer's update.

## Maintainer interpretation question — stale revocation lists

Spec 05 §5.4 allows a list more than one hour but no more than 24 hours stale
to proceed with outcomes capped at `ALLOW_WITH_CAUTION` after refresh fails.
Spec 11 REVOKE-06 describes an expired list older than one hour as a failure
that must be refreshed. The boundaries also differ at exactly one hour:
Spec 05 includes 3600 seconds in its first interval, while Spec 11 defines
its intervals using strict `< 1h` and `> 1h` wording.

These draft texts do not give a single expected result for the full one-to-24
hour range. Maintainers should clarify whether REVOKE-06 is intended to defer
to Spec 05's staleness policy, or to impose a stricter conformance result, and
define the exact one-hour boundary. Until clarified, a conformance test should
not choose one interpretation as normative. This note records the ambiguity;
it does not resolve it or propose a normative change.
