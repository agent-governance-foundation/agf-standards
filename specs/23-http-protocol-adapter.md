# Specification 23: Protocol Adapters (HTTP/REST Gateway)

**Version:** 0.1.0 (Draft)
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Adapter  

## 1. Introduction

`POST /v1/decide` (Spec 10) is protocol-agnostic: it evaluates a delegation chain against an action and returns a decision. It says nothing about how that action reached AGF in the first place. A **protocol adapter** is a component that sits in front of a specific wire protocol — MCP, a REST/GraphQL API, A2A, a browser session — translates that protocol's requests into `/v1/decide` calls, and forwards or blocks the underlying traffic based on the result.

Specs 21 and 22 defined the first two protocol adapters, the MCP Gateway and the A2A Gateway. This spec defines the third: the **HTTP Gateway**, which fronts a downstream generic HTTP/REST API. Other protocols (GraphQL specifically, browser agents) remain out of scope.

## 2. Core Principle

**The adapter is a proxy, not a policy engine.** All authorization logic still runs through the single `/v1/decide` pipeline (quota, HITL, webhooks, audit — Spec 07). The adapter's only jobs are: (1) recognize which incoming requests represent a governable action, (2) translate that action into a `DecideRequest`, and (3) forward or reject the underlying HTTP traffic based on the answer. This is identical to Spec 21 §2 and Spec 22 §2 — every adapter for every protocol converges on the same pipeline.

## 2.1 Why This Adapter Differs From MCP and A2A

MCP and A2A are both JSON-RPC-over-a-single-POST-endpoint protocols with a small fixed vocabulary of named methods — that is why their gateways decision-gate specific method names (`tools/call`, `message/send`) and use a JSON-RPC error envelope (`{"jsonrpc":"2.0","error":{...}}` in an HTTP `200`). Generic HTTP/REST has no such fixed vocabulary or envelope: it is arbitrary verbs on arbitrary paths with arbitrary body content-types (JSON, form-encoded, multipart, binary, whatever the downstream API expects). Two consequences follow directly:

1. **Classification is by HTTP verb semantics, not named methods.** Per RFC 7231 §4.2.1, `GET`/`HEAD`/`OPTIONS` are "safe" methods (must not have side effects) — this gateway treats them as passthrough, exactly like MCP/A2A treat their own read-only/discovery methods. `POST`/`PUT`/`PATCH`/`DELETE` are "unsafe" (can mutate) and are decision-gated.
2. **Errors use real HTTP status codes, not a JSON-RPC envelope.** A generic HTTP client understands and expects real status codes — unlike an MCP/A2A JSON-RPC client, which specifically needs JSON-RPC-shaped errors because that is its protocol's contract. This is the correct design for this adapter, not a workaround.

## 3. Gateway Registration

Before any traffic can flow, an org registers a downstream HTTP/REST API as a gateway: `POST /v1/http-gateways` (growth tier and above).

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Human-readable label |
| `target_url` | Yes | The upstream API's base URL (`http://` or `https://`); the proxy appends the downstream request path to this, stripped of any trailing slash |
| `audience` | Yes | The `aud` value delegation-chain tokens for this gateway must carry — passed as `DecideRequest.audience` |
| `upstream_auth` | No | Bearer token AGF sends upstream as `Authorization: Bearer <token>`. Encrypted at rest, never echoed back in any response |
| `log_request_body` | No, default `false` | Whether the raw request body of a decision-gated call is captured into the decision's audit context. Default off — request bodies can carry secrets or PII, so capturing it is an explicit org opt-in, not a default. Analog of MCP Gateway's `log_tool_arguments` / A2A Gateway's `log_message_content` |
| `timeout_ms` | No, default `30000` | Upstream request timeout |
| `enabled` | No, default `true` | Gateways can be disabled without deleting them |

Full CRUD (`GET`/`POST`/`PATCH`/`DELETE /v1/http-gateways/{id}`) follows the same conventions as `/v1/mcp-gateways` (Spec 21 §3) and `/v1/a2a-gateways` (Spec 22 §3). `POST /v1/http-gateways/{id}/test` sends a plain `GET` to `target_url` and reports reachability — the safest possible probe, since `GET` is by definition a safe method; it never invokes a decision or writes an audit artifact.

## 4. The Proxy Route

`ANY /http/{gateway_id}/{downstream_path}` (`GET`/`HEAD`/`OPTIONS`/`POST`/`PUT`/`PATCH`/`DELETE`) is mounted **unversioned** (not under `/v1/`) — this gateway fronts an arbitrary external API with its own path structure and versioning, distinct from AGF's own API versioning, same reasoning as Spec 21 §4 and Spec 22 §4. It requires the same authentication as every other AGF route (`X-AGF-Key` or `Authorization: Bearer`); an unauthenticated caller cannot reach any gateway, including passthrough methods.

### 4.1 Method Classification

| HTTP method | Classification | `action.type` | `action.resource` |
|---|---|---|---|
| `GET`, `HEAD`, `OPTIONS` | Passthrough | — | — |
| `POST`, `PUT`, `PATCH`, `DELETE` | Decision-gated | the lowercased verb (`"post"`, `"put"`, `"patch"`, `"delete"`) | the raw downstream request path, e.g. `/invoices/123` |

Passthrough methods are forwarded directly once the caller's AGF credentials are validated — no chain, no `/v1/decide` call, no audit artifact. `action.type` being the literal lowercased verb is the simplest, most defensible generic mapping: it lets an org's policy author write rules keyed on the verb without AGF needing to guess intent the way MCP's `tools/call`/A2A's `message/send` conventions do. `action.resource` being the raw request path is possible here in a way it wasn't for MCP/A2A precisely because REST has a native path concept — those two protocols needed ad hoc conventions (tool name, `metadata.skill_id`) to fake one.

### 4.2 Delegation Chain Transport

Identical mechanism to Spec 21 §4.2 / Spec 22 §4.2: this adapter has no protocol-native field for a delegation chain, so it travels as the same stopgap header:

```
X-AGF-Chain: ["<jwt_1>", "<jwt_2>", ...]
```

Required only on decision-gated (unsafe-method) calls; absent or unparseable on such a call is rejected before any upstream traffic is sent (§4.4).

### 4.3 Decision Outcome Mapping

For a decision-gated request, the adapter builds a `DecideRequest` (chain from §4.2, `audience` from the gateway's registered audience, `context` including `http_method` and, if `log_request_body` is enabled, `http_request_body`) and calls the same decision pipeline `/v1/decide` uses internally — full quota, HITL, webhook, and audit-artifact behavior applies identically to HTTP-gateway-routed decisions.

- **ALLOW / ALLOW_WITH_CAUTION** → the original request is forwarded upstream verbatim (headers, query string, and raw body bytes); the response carries an `X-AGF-Artifact-ID` header so the caller can correlate the forwarded response with the audit trail.
- **DENY / REVIEW_REQUIRED / quota-exceeded / service unavailable** → the call is never forwarded upstream. The caller receives a real HTTP error (§4.4).

### 4.4 Error Handling

Unlike Spec 21/22, this adapter does not wrap failures in a protocol envelope — a generic HTTP client speaks plain HTTP and expects a plain HTTP status code.

| Condition | Status | Body |
|---|---|---|
| Unknown `gateway_id` | 404 | `{"error": {"code": "HTTP_GATEWAY_NOT_FOUND", ...}}` (standard AGF error shape) |
| Gateway `enabled = false` | 403 | `{"error": "AGF_GATEWAY_DISABLED", "message": ...}` |
| Decision-gated call, missing/unparseable `X-AGF-Chain` | 401 | `{"error": "AGF_CHAIN_REQUIRED", "message": ...}` |
| DENY / REVIEW_REQUIRED decision | 403 | `{"error": "AGF_DECISION_DENY"` or `"AGF_DECISION_REVIEW_REQUIRED", "message": ..., "artifact_id": ..., "approval_request_id": ...}` |
| Quota exceeded / service unavailable / PDP failure (`decision=None`) | whatever `perform_decision()` returned (e.g. 429, 503) | `perform_decision()`'s own fallback body, forwarded as-is — not reinvented here |
| Upstream blocked by SSRF policy | 502 | `{"error": "AGF_UPSTREAM_BLOCKED", "message": "Upstream blocked by SSRF policy"}` — checked at request time in addition to the creation-time 422 check, since DNS can change after the gateway is registered. Uses the same `check_outbound_url()` / `SSRFBlocked` guard as the MCP and A2A gateways |
| Upstream unreachable | 502 | `{"error": "AGF_UPSTREAM_UNREACHABLE", ...}` |
| Upstream timeout | 504 | `{"error": "AGF_UPSTREAM_TIMEOUT", ...}` |

On ALLOW (or passthrough), the upstream's exact status code, headers (minus hop-by-hop headers — `Connection`, `Transfer-Encoding`, `Keep-Alive`, and `Content-Length`, which is recomputed rather than copied), and raw body bytes are proxied verbatim. This must work for any content-type — JSON, form-encoded, multipart, plain text, binary — since this adapter makes no assumption about what the downstream API expects or returns.

### 4.5 What Is Not Redacted

Passthrough (`GET`/`HEAD`/`OPTIONS`) responses are forwarded verbatim, including whatever the upstream API's own access control already decided to expose. The gateway's `enabled`/`audience`/chain checks gate whether AGF forwards traffic to a given upstream at all; they are not a replacement for the upstream API's own resource-level access control on non-decision-gated methods. Identical to Spec 21 §4.5 / Spec 22 §4.6.

## 5. Non-Goals / Scope Limits (v1)

This adapter is deliberately narrower than a general-purpose API gateway:

- **No per-route configuration.** Classification is purely verb-based (§4.1) — there is no way to override this per-path yet. An org cannot, for example, mark a specific `POST /webhooks/ping` endpoint as passthrough, or force a specific `GET /export` endpoint to be decision-gated. Every unsafe-method request through a given gateway is gated the same way.
- **No path-parameter normalization.** `action.resource` is the raw request path (§4.1) with no template extraction: `/invoices/123` and `/invoices/456` are currently two different resource strings. A policy author who wants a single rule matching `/invoices/*` cannot write one against `action.resource` today — they would need one rule per concrete id, or a rule that ignores `action.resource` entirely and gates on `action.type`/`audience` alone. This is a real limitation, not a nuance — flagged here honestly rather than glossed over. A v2 path-template feature (registering `/invoices/{id}` on the gateway and having the adapter emit the templated form as `action.resource`) is the natural fix; not built.
- **No WebSocket/SSE support.** The proxy is a single request/response passthrough. Long-lived connections (WebSocket upgrades, Server-Sent Events) are not supported — a request that attempts either will be treated as a normal HTTP request/response by the underlying `httpx` client and will not behave as the caller expects.
- **No GraphQL awareness.** A GraphQL endpoint fronted by this gateway is just an opaque `POST` from the adapter's point of view — `action.resource` would be the GraphQL endpoint's path (typically `/graphql` for every operation), not the query/mutation name inside the body. Query-level classification is not implemented.
- **Retries.** Deliberately absent, same reasoning as Spec 21/22 — an unsafe-method request is not known to be idempotent, and AGF cannot assume it is safe to re-execute a call that may already have taken effect upstream.
- **Per-endpoint auth negotiation.** `upstream_auth` is a single static bearer token per gateway, identical to the MCP and A2A gateways' stopgap (Spec 21 §7, Spec 22 §7). Downstream APIs requiring API keys in custom headers, HMAC signing, mTLS, or OAuth2 client-credentials flows are not supported.

## 6. Relationship to Spec 07 (Audit Trail)

A decision-gated HTTP-gateway call produces exactly the same audit artifact a direct `/v1/decide` call would, with `context.http_method` recording which verb triggered it (the HTTP analog of Spec 21 §6's `context.mcp_method` and Spec 22 §6's `context.a2a_method`). No HTTP-gateway-specific audit schema exists or is needed.

## 7. Open Items

- **Path-template / route-registration feature.** See §5 — the biggest usability gap for policy authors today. Candidate v2 design: let a gateway optionally register a set of path templates (`/invoices/{id}`, `/users/{id}/orders`); the adapter matches the incoming path against them and emits the templated form as `action.resource` when a match is found, falling back to the raw path otherwise.
- **Per-route classification override.** See §5 — today every unsafe method on every path behind a gateway is gated identically; there is no way to carve out exceptions (e.g. a `POST /webhooks/ping` health-check endpoint) without gating them, or to gate a `GET` that the org considers sensitive.
- **GraphQL-aware classification.** Not built. A GraphQL API behind this gateway is opaque to it (§5); a dedicated GraphQL adapter (query/mutation-name-aware, like MCP's `tools/call` awareness) is a distinct future adapter, not a mode of this one.
- **WebSocket/SSE support.** Not built (§5).
- **Per-endpoint auth negotiation.** Not built (§5) — mirrors the same open item on the MCP and A2A sides.
- **Other protocol adapters** (GraphQL, browser agents). None exist. See Spec 21 §7 / Spec 22 §7 for the same open item.

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
