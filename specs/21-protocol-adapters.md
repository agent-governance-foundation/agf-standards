# Specification 21: Protocol Adapters (MCP Gateway)

**Version:** 0.2.0 (Draft)
**Status:** Working Draft  
**Supersedes:** 0.1.0  
**Layer:** Adapter  

## 1. Introduction

`POST /v1/decide` (Spec 10) is protocol-agnostic: it evaluates a delegation chain against an action and returns a decision. It says nothing about how that action reached AGF in the first place. A **protocol adapter** is a component that sits in front of a specific wire protocol — MCP, a REST/GraphQL API, A2A, a browser session — translates that protocol's requests into `/v1/decide` calls, and forwards or blocks the underlying traffic based on the result.

This spec defines the first protocol adapter: the **MCP Gateway**, which fronts a downstream MCP (Model Context Protocol) server. Other protocols (A2A, generic HTTP/REST, browser agents) are out of scope for this version.

## 2. Core Principle

**The adapter is a proxy, not a policy engine.** All authorization logic still runs through the single `/v1/decide` pipeline (quota, HITL, webhooks, audit — Spec 07). The adapter's only jobs are: (1) recognize which incoming requests represent a governable action, (2) translate that action into a `DecideRequest`, and (3) forward or reject the underlying protocol traffic based on the answer. An adapter that duplicated decision logic instead of calling `/v1/decide` would defeat the point of having one authorization engine — every adapter for every protocol converges on the same pipeline.

## 3. Gateway Registration

Before any traffic can flow, an org registers a downstream MCP server as a gateway: `POST /v1/mcp-gateways` (growth tier and above).

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Human-readable label |
| `target_url` | Yes | The upstream MCP server's JSON-RPC endpoint (`http://` or `https://`) |
| `audience` | Yes | The `aud` value delegation-chain tokens for this gateway must carry — passed as `DecideRequest.audience` |
| `upstream_auth` | No | Bearer token AGF sends upstream as `Authorization: Bearer <token>`. Encrypted at rest, never echoed back in any response |
| `log_tool_arguments` | No, default `false` | Whether raw `tools/call` arguments are captured into the decision's audit context. Default off — tool arguments can carry secrets or PII, so capturing them is an explicit org opt-in, not a default |
| `timeout_ms` | No, default `30000` | Upstream request timeout |
| `enabled` | No, default `true` | Gateways can be disabled without deleting them |

Full CRUD (`GET`/`POST`/`PATCH`/`DELETE /v1/mcp-gateways/{id}`) follows the same conventions as `/v1/siem-destinations` and `/v1/outbound-webhooks` (Spec 10's illustrative multi-service envelope does not apply here). `POST /v1/mcp-gateways/{id}/test` sends a `tools/list` probe to the upstream server and reports reachability; it never invokes a decision or writes an audit artifact.

## 4. The Proxy Route

`POST /mcp/{gateway_id}` is mounted **unversioned** (not under `/v1/`) — MCP has its own `protocolVersion` handshake, distinct from AGF's own API versioning. It requires the same authentication as every other AGF route (`X-AGF-Key` or `Authorization: Bearer`); an unauthenticated caller cannot reach any gateway, including passthrough methods.

### 4.1 Method Classification

Not every MCP method represents a governable action. Two are decision-gated; everything else is passthrough.

| Method | Classification | `action.type` | `action.resource` |
|---|---|---|---|
| `tools/call` | Decision-gated | `execute` | `params.name` (the tool name) |
| `resources/read` | Decision-gated | `read` | `params.uri` |
| `initialize`, `tools/list`, `resources/list`, `prompts/list`, `prompts/get`, `ping`, `notifications/*` | Passthrough | — | — |

Passthrough methods are forwarded directly once the caller's AGF credentials are validated — no chain, no `/v1/decide` call, no audit artifact. This list is deliberately narrow: `resources/read` is decision-gated (not passthrough) because it is the method most likely to exfiltrate data the caller shouldn't see, and `tools/call` is decision-gated because it is the method most likely to have side effects. As MCP evolves, new methods should be added to the passthrough list only if they are provably read-only and non-sensitive; the default for an unrecognized method is to treat it as passthrough (forward it), not to invent a new decision category — inventing new `action.type` values here would fragment policy authoring away from Spec 10's action model.

### 4.2 Delegation Chain Transport

MCP's JSON-RPC envelope has no field for a delegation chain. Until OAuth 2.1 integration (§7) provides a native carrier, the chain travels as a stopgap header:

```
X-AGF-Chain: ["<jwt_1>", "<jwt_2>", ...]
```

a JSON array of the same JWT strings `DecideRequest.chain` expects. Required on every decision-gated call; absent or unparseable on a decision-gated call is rejected before any upstream traffic is sent (§4.4).

### 4.3 Decision Outcome Mapping

For a decision-gated method, the adapter builds a `DecideRequest` (chain from §4.2, `audience` from the gateway's registered audience, `context` including `mcp_method` and, if present, the `Mcp-Session-Id` header) and calls the same decision pipeline `/v1/decide` uses internally — full quota, HITL, webhook, and audit-artifact behavior applies identically to MCP-routed decisions.

- **ALLOW** → the original JSON-RPC request is forwarded upstream verbatim; the response carries an `X-AGF-Artifact-ID` header so the caller can correlate the forwarded response with the audit trail.
- **DENY / REVIEW_REQUIRED / quota-exceeded / service unavailable** → the call is never forwarded upstream. The caller receives a JSON-RPC error (§4.4), not the raw HTTP status a direct `/v1/decide` caller would see — an MCP client speaks JSON-RPC and needs a JSON-RPC-shaped answer regardless of why authorization failed.

The gateway emits an Execution Receipt for every mediated decision per Spec 07 §10.3 — `not_executed` for blocked calls, `executed` when the upstream responded, `unknown` on timeout or transport error — and returns its id in an `X-AGF-Receipt-ID` response header alongside `X-AGF-Artifact-ID`. Receipt persistence is best-effort: it never fails or delays the mediated call.

### 4.4 Error Handling

Once a gateway is resolved from the URL, every failure — bad request shape, disabled gateway, missing chain, a non-ALLOW decision, upstream unreachable, upstream timeout — surfaces as a JSON-RPC error object in a `200` response, not an arbitrary HTTP status. An MCP client only knows how to interpret JSON-RPC errors; forcing it to branch on HTTP status codes it wasn't built to expect would break more integrations than it would help.

| Condition | Code | Notes |
|---|---|---|
| Unknown `gateway_id` | HTTP 404 | The one exception — this is a URL-routing failure, not a protocol-level one |
| Batch request (JSON array body) | -32600 | JSON-RPC batching is not supported |
| Missing/invalid `method` | -32600 | Invalid Request |
| Gateway `enabled = false` | -32001 | |
| Decision-gated call, missing/unparseable `X-AGF-Chain` | -32001 | |
| Non-ALLOW decision | -32000 | `data.artifact_id` / `data.approval_request_id` included where applicable |
| Upstream timeout | -32000 | Reported once; **never retried** — a `tools/call` is not known to be idempotent, and AGF cannot assume it is safe to re-execute a tool that may already have taken effect upstream |
| Upstream unreachable | -32000 | |
| Upstream blocked by SSRF policy | -32000 | `target_url`'s hostname resolved to a non-globally-routable address (private/loopback/link-local/metadata); checked at request time in addition to the creation-time 422 check, since DNS can change after the gateway is registered |

### 4.5 What Is Not Redacted

`tools/list`, `resources/list`, and similar passthrough responses are forwarded verbatim, including whatever the upstream server's own access control already decided to expose. The gateway's `enabled`/`audience`/chain checks gate whether AGF forwards traffic to a given upstream at all; they are not a replacement for the upstream server's own resource-level access control on non-decision-gated methods.

## 5. Non-Goals

- **Session state.** The gateway does not track MCP session lifecycle beyond forwarding `Mcp-Session-Id` verbatim; session continuity is the upstream server's concern.
- **Protocol translation.** The gateway does not reshape MCP semantics into some AGF-native format — the JSON-RPC envelope is forwarded byte-for-byte on the allowed path.
- **Retries.** Deliberately absent (§4.4) — see the upstream-timeout row.

## 6. Relationship to Spec 07 (Audit Trail)

A decision-gated MCP call produces exactly the same audit artifact a direct `/v1/decide` call would, with `context.mcp_method` recording which MCP method triggered it. No MCP-specific audit schema exists or is needed.

## 7. Open Items

- **OAuth 2.1 for upstream MCP servers.** Not built. `upstream_auth` today is a single static bearer token per gateway; a full OAuth 2.1 client-credentials or token-exchange flow against the upstream server is future work.
- **Other protocol adapters** (A2A, generic REST/GraphQL, browser agents). None exist. The method-classification and error-handling patterns in §4 are intended to generalize, but no other adapter has been built to confirm that.
- **`resources/write`-equivalent methods**, if a future MCP revision adds one, would need the same decision-gating treatment as `tools/call`.

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
| 0.2.0 | 2026-07-15 | Gateway emits Execution Receipts (Spec 07 §10.3) with `X-AGF-Receipt-ID` response header |
