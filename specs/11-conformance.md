# Specification 11: Conformance Test Suite

**Version:** 0.1.0 (Draft)  
**Status:** Working Draft  
**Supersedes:** 0.1.1

## 1. Introduction

Conformance testing ensures implementations correctly follow the specifications. This document defines the test suite structure, test cases, and conformance levels.

## 2. Conformance Levels

| Level | Description | Requirements |
|-------|-------------|--------------|
| Level 1 | Basic | Delegation token format, chain validation |
| Level 2 | Standard | + Revocation, trust score, audit |
| Level 3 | Full | + All features, cross-org, performance |

## 3. Test Categories

### 3.1 Delegation Token Tests (Level 1)

| Test ID | Description | Expected |
|---------|-------------|----------|
| TOKEN-01 | Create valid token | Success |
| TOKEN-02 | Verify valid token signature | Pass |
| TOKEN-03 | Detect invalid signature | Fail with `INVALID_SIGNATURE` |
| TOKEN-04 | Detect expired token | Fail with `EXPIRED` |
| TOKEN-05 | Detect wrong audience | Fail with `AUDIENCE_MISMATCH` |
| TOKEN-06 | Detect missing required claim | Fail with `INVALID_REQUEST` |
| TOKEN-07 | Validate scope format | Pass for valid, fail for invalid |
| TOKEN-08 | Enforce max token size (8KB) | Fail for oversized |

### 3.2 Chain Validation Tests (Level 1)

| Test ID | Description | Expected |
|---------|-------------|----------|
| CHAIN-01 | Valid chain of 3 tokens | Pass |
| CHAIN-02 | Broken continuity (iss/sub mismatch) | Fail with `CHAIN_BROKEN` |
| CHAIN-03 | Chain with expired token | Fail with `EXPIRED` |
| CHAIN-04 | Chain with revoked token | Fail with `REVOKED` |
| CHAIN-05 | Scope intersection correctly computed | Pass |
| CHAIN-06 | Action outside effective scope | Fail with `SCOPE_INSUFFICIENT` |
| CHAIN-07 | Chain exceeding max_depth | Fail with `DEPTH_EXCEEDED` |
| CHAIN-08 | Empty chain | Fail with `INVALID_REQUEST` |
| CHAIN-09 | Constraint violation in token | Fail with `CONSTRAINT_VIOLATION` |
| CHAIN-10 | Scope canonicalization applied before intersection | Pass (equivalent scopes treated as equal) |

### 3.3 Trust Score Tests (Level 2)

| Test ID | Description | Expected |
|---------|-------------|----------|
| TRUST-01 | Depth 1, age 0 → score 100 | 100 |
| TRUST-02 | Depth 3 → score 90 | 90 |
| TRUST-03 | Age 4 hours → score 92 | 92 |
| TRUST-04 | Depth 3 + age 4h → score 82 | 82 |
| TRUST-05 | Revoked delegation → score 0 | 0 |
| TRUST-06 | Expired delegation → score 0 | 0 |
| TRUST-07 | Stale revocation list → −20 penalty | 80 − 20 = 60 |
| TRUST-08 | Trust score never below 0 | `max(0, score)` |

### 3.4 Revocation Tests (Level 2)

| Test ID | Description | Expected |
|---------|-------------|----------|
| REVOKE-01 | Check non-revoked delegation | `is_revoked = false` |
| REVOKE-02 | Check revoked delegation | `is_revoked = true` |
| REVOKE-03 | Branch cut: parent revoked | child also revoked |
| REVOKE-04 | Branch cut: sibling not affected | sibling not revoked |
| REVOKE-05 | Revocation list stale (< 1h) | warning, still usable |
| REVOKE-06 | Revocation list expired (> 1h) | fail, must refresh |
| REVOKE-07 | Revocation list signature invalid | fail |
| REVOKE-08 | Multiple revocations in list | all correctly detected |

### 3.5 Risk Layer Tests (Level 2)

| Test ID | Description | Expected |
|---------|-------------|----------|
| RISK-01 | Inherent risk mapping | correct value |
| RISK-02 | Environmental risk (time) | modifier applied |
| RISK-03 | Environmental risk (location) | modifier applied |
| RISK-04 | Environmental risk (velocity) | modifier applied |
| RISK-05 | Trust weight calculation | depends on declared weighting strategy |
| RISK-05a | Linear: `trust_score / 100` | correct per formula |
| RISK-05b | Conservative: `(trust_score / 100)²` | correct per formula |
| RISK-05c | Permissive: `sqrt(trust_score / 100)` | correct per formula |
| RISK-06 | Final risk combination | `inherent + (env × weight)` |
| RISK-07 | Risk caps at 100 | max 100 |
| RISK-08 | Decision mapping based on risk | ALLOW / CAUTION / DENY |

**Test setup for RISK-05:**

The conformance test suite MUST accept a `--weighting` parameter (`linear`, `conservative`, `permissive`). Each weighting mode is tested independently. An implementation passes RISK-05 if it correctly implements its declared weighting strategy.

```bash
pytest tests/test_risk.py -k RISK-05 --weighting=conservative
```

### 3.6 Policy Tests (Level 2)

| Test ID | Description | Expected |
|---------|-------------|----------|
| POLICY-01 | Simple allow policy | `allow = true` |
| POLICY-02 | Simple deny policy | `allow = false` |
| POLICY-03 | Policy with conditions | evaluates correctly |
| POLICY-04 | Multiple policies: deny overrides allow | `DENY` |
| POLICY-05 | Policy versioning | correct version used |
| POLICY-06 | Missing policy | fail with `NOT_FOUND` |
| POLICY-07 | Invalid policy syntax | fail with `INVALID_POLICY` |
| POLICY-08 | Token with `policy_version` claim | exact version used |
| POLICY-09 | `policy_version` not found, trusted issuer | fallback with `ALLOW_WITH_CAUTION` |
| POLICY-10 | `policy_version` not found, untrusted issuer | fail with `POLICY_VERSION_NOT_FOUND` |

### 3.7 Audit Tests (Level 2)

| Test ID | Description | Expected |
|---------|-------------|----------|
| AUDIT-01 | Artifact created for every decision | exists |
| AUDIT-02 | Artifact contains request | matches |
| AUDIT-03 | Artifact contains response | matches |
| AUDIT-04 | Artifact contains policy version | present |
| AUDIT-05 | Artifact contains revocation state | present |
| AUDIT-06 | Artifact signature valid | passes |
| AUDIT-07 | Artifact retrieval by ID | returns correct |
| AUDIT-08 | Artifact search with filters | returns matching |

### 3.8 Identity Tests (Level 3)

| Test ID | Description | Expected |
|---------|-------------|----------|
| ID-01 | Register new agent | returns DID |
| ID-02 | Resolve DID to document | matches |
| ID-03 | Update DID document | updated |
| ID-04 | Key rotation | new key verified |
| ID-05 | Key revocation | key invalid |
| ID-06 | Cross-domain resolution | works |
| ID-07 | DID with unknown controller | fail |

### 3.9 Performance Tests (Level 3)

| Test ID | Description | Requirement |
|---------|-------------|-------------|
| PERF-01 | Trust evaluator latency (P99), depth = 3 | < 30ms |
| PERF-01a | Trust evaluator latency (P99), depth = 10 | < 80ms |
| PERF-02 | PDP latency (P99), depth = 3, no caching | < 100ms |
| PERF-02a | PDP latency (P99), depth = 10, no caching | < 250ms |
| PERF-03 | Throughput (requests/sec), depth = 3 | > 1000 |
| PERF-03a | Throughput (requests/sec), depth = 10 | > 500 |
| PERF-04 | Chain length scaling | sub-linear (amortized with caching) |
| PERF-05 | Revocation list size scaling (10k entries) | < 2× baseline latency |
| PERF-06 | Concurrent requests (100 clients) | < 20% latency degradation |

**Performance analysis at max depth (10 tokens):**

| Operation | Cost per token | Total at depth 10 |
|-----------|----------------|-------------------|
| Signature verification (ES256) | ~1ms | ~10ms |
| Expiration check | ~0.01ms | ~0.1ms |
| Revocation check (hash set) | ~0.005ms | ~0.05ms |
| Scope intersection | ~0.02ms | ~0.2ms |
| DID resolution (first + cached) | ~5ms + ~0.1ms | ~5.5ms |
| Policy evaluation (OPA) | ~15ms (one-time) | ~15ms |
| **Estimated P99 total** | | **~31ms** |

The 100ms budget for depth = 3 is achievable. For depth = 10, 250ms is a realistic target. Implementations SHOULD:

- Cache DID resolutions aggressively (TTL 300s)
- Use a hash-set revocation store, not a database query
- Parallelize independent per-token checks
- Document actual measured performance for each deployment

If an implementation cannot meet these targets, it MUST document its measured performance and MAY declare a lower maximum chain depth in its conformance certificate (e.g., "Conformance Level 2, max chain depth = 5").

### 3.10 Security Tests (Level 3)

| Test ID | Description | Requirement |
|---------|-------------|-------------|
| SEC-01 | Replay attack prevention | rejected |
| SEC-02 | Token tampering | detected |
| SEC-03 | Revocation list tampering | detected |
| SEC-04 | Policy injection | prevented |
| SEC-05 | Privilege escalation | prevented |
| SEC-06 | Denial of service | rate limited |

## 4. Test Environment

### 4.1 Setup

```bash
# Clone conformance tests
git clone https://github.com/agf/conformance
cd conformance

# Install dependencies
pip install -r requirements.txt

# Configure endpoint
export AGF_ENDPOINT="https://pdp.acme.com"

# Run tests
pytest tests/ -v --level=2
```

> **Note:** The `agf/conformance` repository is under development. Tests will be available at the time of the specification 1.0.0 release. Early implementers should contact the foundation for access to the beta test suite.

### 4.2 Test Results

Output format:

```
Test Session Summary
====================
Level 1: 25/25 passed
Level 2: 38/40 passed (2 skipped)
Level 3: 12/12 passed

Overall: 75/77 passed (97.4%)
```

## 5. Conformance Certification

### 5.1 Process

1. Implementer runs conformance test suite
2. Achieves required level (1, 2, or 3)
3. Submits results to foundation
4. Foundation reviews (may request independent test)
5. Certification issued (valid for 1 year)

### 5.2 Certification Levels

| Level | Use Case |
|-------|----------|
| Level 1 | Basic agent deployments |
| Level 2 | Enterprise production |
| Level 3 | Cross-org federation, regulated industries |

## 6. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
