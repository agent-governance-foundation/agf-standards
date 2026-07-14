# Specification 22: Protocol Adapters (A2A Gateway)

**Version:** 0.1.0 (Draft)
**Status:** Working Draft  
**Supersedes:** None  
**Layer:** Adapter  

## 1. Introduction

`POST /v1/decide` (Spec 10) is protocol-agnostic: it evaluates a delegation chain against an action and returns a decision. It says nothing about how that action reached AGF in the first place. A **protocol adapter** is a component that sits in front of a specific wire protocol — MCP, a REST/GraphQL API, A2A, a browser session — translates that protocol's requests into `/v1/decide` calls, and forwards or blocks the underlying traffic based on the result.

Spec 21 defined the first protocol adapter, the MCP Gateway. This spec defines the second: the **A2A Gateway**, which fronts a downstream A2A (Agent2Agent protocol, a2a-protocol.org, version 1.0.0) agent. Both adapters share the same architectural pattern — a registered gateway, an unversioned JSON-RPC proxy route, method classification into decision-gated vs. passthrough, and the same `/v1/decide` pipeline underneath. Other protocols (generic HTTP/REST, browser agents) remain out of scope.

## 2. Core Principle

**The adapter is a proxy, not a policy engine.** All authorization logic still runs through the single `/v1/decide` pipeline (quota, HITL, webhooks, audit — Spec 07). The adapter's only jobs are: (1) recognize which incoming requests represent a governable action, (2) translate that action into a `DecideRequest`, and (3) forward or reject the underlying protocol traffic based on the answer. This is identical to Spec 21 §2 — every adapter for every protocol converges on the same pipeline.

## 3. Gateway Registration

Before any traffic can flow, an org registers a downstream A2A agent as a gateway: `POST /v1/a2a-gateways` (growth tier and above).

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Human-readable label |
| `target_url` | Yes | The upstream A2A agent's JSON-RPC endpoint (`http://` or `https://`) |
| `audience` | Yes | The `aud` value delegation-chain tokens for this gateway must carry — passed as `DecideRequest.audience` |
| `upstream_auth` | No | Bearer token AGF sends upstream as `Authorization: Bearer <token>`. Encrypted at rest, never echoed back in any response |
| `log_message_content` | No, default `false` | Whether raw `message/send` / `message/sendStreaming` message content is captured into the decision's audit context. Default off — message content can carry secrets or PII, so capturing it is an explicit org opt-in, not a default. Analog of MCP Gateway's `log_tool_arguments` — A2A calls its payload "message content" rather than "tool arguments" |
| `timeout_ms` | No, default `30000` | Upstream request timeout |
| `enabled` | No, default `true` | Gateways can be disabled without deleting them |

Full CRUD (`GET`/`POST`/`PATCH`/`DELETE /v1/a2a-gateways/{id}`) follows the same conventions as `/v1/mcp-gateways` (Spec 21 §3). `POST /v1/a2a-gateways/{id}/test` sends an `agentCard/get` probe to the upstream agent and reports reachability — chosen because it is A2A's safe, read-only discovery method, analogous to MCP's `tools/list` probe; it never invokes a decision or writes an audit artifact.

## 4. The Proxy Route

`POST /a2a/{gateway_id}` is mounted **unversioned** (not under `/v1/`) — A2A has its own protocol versioning, distinct from AGF's own API versioning, same reasoning as Spec 21 §4. It requires the same authentication as every other AGF route (`X-AGF-Key` or `Authorization: Bearer`); an unauthenticated caller cannot reach any gateway, including passthrough methods.

### 4.1 Method Classification

Not every A2A JSON-RPC method represents a governable action. Two are decision-gated; everything else is passthrough.

| Method | Classification | `action.type` | `action.resource` |
|---|---|---|---|
| `message/send` | Decision-gated | `execute` | `message.metadata.skill_id`, or the literal string `"message"` if absent |
| `message/sendStreaming` | Decision-gated | `execute` | Same as `message/send` |
| `tasks/get`, `tasks/list`, `agentCard/get` | Passthrough | — | — |
| `tasks/cancel`, `tasks/subscribe` | Passthrough | — | — |
| `taskPushNotificationConfig/create`, `taskPushNotificationConfig/get`, `taskPushNotificationConfig/list`, `taskPushNotificationConfig/delete` | Passthrough | — | — |

Passthrough methods are forwarded directly once the caller's AGF credentials are validated — no chain, no `/v1/decide` call, no audit artifact. `message/send` and `message/sendStreaming` are decision-gated because they are the methods that cause the remote agent to actually do something (A2A's own spec language: "work-initiating"); everything else is either read-only discovery or task/config management.

`tasks/cancel` and the `taskPushNotificationConfig/*` CRUD methods are treated as passthrough for v1 as a **deliberate, narrow scope choice** — mirrors Spec 21's own reasoning: gate only what executes work or exposes data. This is a candidate for tightening later (a malicious or misconfigured caller could still cancel another party's task, or redirect push notifications, without a decision pass) — it is not a permanent judgment that these methods are safe to leave ungated forever.

**`action.resource` derivation is looser than MCP's.** MCP's `tools/call` has a mandated `params.name` field naming exactly what's being invoked. A2A has no equivalent — `Message` objects carry `parts` (text/raw/url/data) but no canonical "what is this a call to" field. This gateway uses `message.metadata.skill_id` as a pragmatic convention: if the caller tags which skill they're invoking via `metadata.skill_id` on the outgoing message, policy can be written against that resource name; otherwise the resource falls back to the literal string `"message"`, meaning policy can only distinguish `message/send` calls by gateway/audience, not by what's being requested within them. Orgs that need finer-grained resource-level policy on A2A traffic should have their calling code populate `metadata.skill_id`.

### 4.2 Delegation Chain Transport

Identical mechanism to Spec 21 §4.2: A2A's JSON-RPC envelope has no field for a delegation chain, so it travels as the same stopgap header:

```
X-AGF-Chain: ["<jwt_1>", "<jwt_2>", ...]
```

Required on every decision-gated call; absent or unparseable on a decision-gated call is rejected before any upstream traffic is sent (§4.4).

Unlike MCP's `Mcp-Session-Id`, A2A's session-continuity concept — `contextId` — lives **inside** the JSON-RPC body (`message.contextId` / `task.contextId`), not as an HTTP header. It therefore needs no special header-relay logic on this gateway: it flows through naturally with the byte-for-byte body forwarding both adapters already do on the allowed path.

### 4.3 Decision Outcome Mapping

For a decision-gated method, the adapter builds a `DecideRequest` (chain from §4.2, `audience` from the gateway's registered audience, `context` including `a2a_method` and, if `log_message_content` is enabled, `a2a_message_content`) and calls the same decision pipeline `/v1/decide` uses internally — full quota, HITL, webhook, and audit-artifact behavior applies identically to A2A-routed decisions.

- **ALLOW / ALLOW_WITH_CAUTION** → the original JSON-RPC request is forwarded upstream verbatim; the response carries an `X-AGF-Artifact-ID` header so the caller can correlate the forwarded response with the audit trail.
- **DENY / REVIEW_REQUIRED / quota-exceeded / service unavailable** → the call is never forwarded upstream. The caller receives a JSON-RPC error (§4.4) whose `error.data` includes `decision`, `artifact_id`, and `approval_request_id` directly, consistent with Spec 21's MCP Gateway.

### 4.4 Error Handling

Once a gateway is resolved from the URL, every failure — bad request shape, disabled gateway, missing chain, a non-ALLOW decision, upstream unreachable, upstream timeout, SSRF-blocked — surfaces as a JSON-RPC error object in a `200` response, not an arbitrary HTTP status. Identical posture to Spec 21 §4.4: an A2A client speaks JSON-RPC and needs a JSON-RPC-shaped answer regardless of why authorization failed.

| Condition | Code | Notes |
|---|---|---|
| Unknown `gateway_id` | HTTP 404 | The one exception — this is a URL-routing failure, not a protocol-level one |
| Batch request (JSON array body) | -32600 | JSON-RPC batching is not supported |
| Missing/invalid `method` | -32600 | Invalid Request |
| Gateway `enabled = false` | -32001 | |
| Decision-gated call, missing/unparseable `X-AGF-Chain` | -32001 | |
| Non-ALLOW decision | -32000 | `data.decision` / `data.artifact_id` / `data.approval_request_id` included directly |
| Upstream timeout | -32000 | Reported once; never retried — `message/send` is not known to be idempotent, and AGF cannot assume it is safe to re-execute a message that may already have taken effect upstream |
| Upstream unreachable | -32000 | |
| Upstream blocked by SSRF policy | -32000 | `target_url`'s hostname resolved to a non-globally-routable address (private/loopback/link-local/metadata); checked at request time in addition to the creation-time 422 check, since DNS can change after the gateway is registered. Uses the same `check_outbound_url()` / `SSRFBlocked` guard as the MCP Gateway |

### 4.5 Streaming Limitation (v1)

`message/sendStreaming` is accepted into the decision-gating classification (§4.1) — a caller invoking it still gets a real `/v1/decide` pass — but the actual **SSE streaming response is not implemented in v1**. If the decision is ALLOW, the gateway proxies the call as a normal single POST/response (whatever the upstream agent returns to a non-streaming POST), rather than opening a Server-Sent Events stream back to the caller. This mirrors Spec 21's own "no SSE" limitation for MCP.

Callers that need real streaming behavior should use `message/send` and poll `tasks/get` instead, until real streaming support ships. This is a known, deliberate v1 gap, not a silent one — see §7.

### 4.6 What Is Not Redacted

`tasks/get`, `tasks/list`, `agentCard/get`, and other passthrough responses are forwarded verbatim, including whatever the upstream agent's own access control already decided to expose. The gateway's `enabled`/`audience`/chain checks gate whether AGF forwards traffic to a given upstream at all; they are not a replacement for the upstream agent's own resource-level access control on non-decision-gated methods. Identical to Spec 21 §4.5.

## 5. Non-Goals

- **Session state.** The gateway does not track A2A task/context lifecycle; `contextId`/`taskId` continuity is the upstream agent's concern (see §4.2 on why no header-relay logic is needed here, unlike MCP's `Mcp-Session-Id`).
- **Protocol translation.** The gateway does not reshape A2A semantics into some AGF-native format — the JSON-RPC envelope is forwarded byte-for-byte on the allowed path.
- **Retries.** Deliberately absent (§4.4) — see the upstream-timeout row.
- **Real SSE streaming.** See §4.5 — `message/sendStreaming` is gated but not actually streamed in v1.
- **Per-agent auth negotiation.** An `AgentCard`'s declared `securitySchemes` (APIKey, HTTP Bearer/Basic, OAuth2, OpenIdConnect, MutualTLS) are not inspected or negotiated; `upstream_auth` is a single static bearer token per gateway, identical to MCP Gateway's stopgap (Spec 21 §7).

## 6. Relationship to Spec 07 (Audit Trail)

A decision-gated A2A call produces exactly the same audit artifact a direct `/v1/decide` call would, with `context.a2a_method` recording which A2A method triggered it (the A2A analog of Spec 21 §6's `context.mcp_method`). No A2A-specific audit schema exists or is needed.

## 7. Open Items

- **Real SSE streaming for `message/sendStreaming`.** Not built (§4.5). Needs a decision on how a decision-gated streaming response should be represented back to the caller — the current single-POST fallback is a stopgap, not a design.
- **Per-agent auth negotiation against `AgentCard.securitySchemes`.** Not built. `upstream_auth` today is a single static bearer token per gateway; real OAuth2/OIDC/mTLS negotiation against what a downstream agent's own `AgentCard` declares is future work (mirrors Spec 21's open OAuth 2.1 item on the MCP side).
- **Tightening `tasks/cancel` / `taskPushNotificationConfig/*` to decision-gated.** Currently passthrough (§4.1) as a narrow v1 scope choice; revisit once real usage patterns for cancellation and push-notification-config abuse are understood.
- **`action.resource` convention (`metadata.skill_id`).** This is a project convention, not part of the A2A spec itself — if the A2A ecosystem converges on a different canonical "what is this a call to" field, this gateway's resource derivation should follow it rather than staying attached to `metadata.skill_id` forever.
- **Other protocol adapters** (generic REST/GraphQL, browser agents). None exist. See Spec 21 §7 for the same open item on the MCP side.

## 8. Change Log

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-07-12 | Initial public working draft |
