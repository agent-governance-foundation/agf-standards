# AGF Standards

**Open specifications for AI agent governance — identity, delegation, authorization, audit, and revocation.**

Enterprises will deploy millions of AI agents. The industry is converging on open protocols for how those agents connect — MCP for tools, A2A for agent-to-agent communication. What has no open standard yet is the layer above: **what an agent is allowed to do, on whose authority, and who is accountable when it acts.**

The Agent Governance Foundation (AGF) standards fill that gap.

## Where AGF sits in the agentic stack

```
┌──────────────────────────────────────────────────┐
│              Applications & AI Agents            │
├──────────────────────────────────────────────────┤
│        AGF — Governance & Accountability         │
│   identity · delegation chains · authorization   │
│   risk · policy · audit · revocation · oversight │
├──────────────────────────────────────────────────┤
│        Agent Protocols — MCP · A2A · HTTP        │
│        (connectivity & interoperability)         │
├──────────────────────────────────────────────────┤
│                Models · Tools · Data             │
└──────────────────────────────────────────────────┘
```

Agent protocols standardize **how agents talk** to tools and to each other. AGF standardizes **what they are permitted to do and who answers for it**. The two layers are complementary: AGF specifications include protocol adapters (Specs 21–23) that apply governance decisions to MCP, A2A, and plain HTTP traffic without modifying those protocols.

## Start here

- **[Vision & Mission](vision-and-mission.md)** — why AGF exists and the model behind it. Read this first.
- **[Complete Authorization Flow](authorization-flow.md)** — end-to-end walkthrough: how an agent gets authority, makes a request, and produces an auditable decision.
- **[Specifications](specs/)** — the standards themselves: 27 specs covering delegation tokens, chains, trust zones, risk, revocation, policy, audit, identity, keys, conformance, emergency procedures, privacy, deployment governance, human oversight, multi-agent coordination, behavioral monitoring, protocol adapters, and cross-domain trust.
- **[Integration Guide](adoption/integration-guide.md)** — connecting AGF to an existing IAM (Okta, Azure AD, LDAP).

## What's in this repository

| Directory | Contents |
|---|---|
| [specs/](specs/) | The AGF specifications (numbered 01–27) |
| [schemas/](schemas/) | Machine-readable schemas (JSON Schema, OpenAPI) extracted from the specs |
| [conformance/](conformance/) | Test vectors and the conformance suite for independent implementations |
| [rfcs/](rfcs/) | Proposals for substantive changes to the specifications |
| [adoption/](adoption/) | Integration guides and the list of known implementations |

## Specification maturity

Every specification carries a status:

| Status | Meaning |
|---|---|
| **Working Draft** | Open for feedback; may change without notice |
| **Candidate** | Feature-complete with machine-readable schemas; seeking implementation experience |
| **Stable** | Proven by at least two independent implementations passing the conformance suite; changes only via the RFC process |
| **Deprecated** | Superseded; kept for reference |

All specifications are currently **Working Draft**. We are actively seeking feedback — file an [issue](../../issues) or open an [RFC](rfcs/).

## Contributing

Editorial fixes are welcome as direct pull requests. Substantive (normative) changes go through the [RFC process](rfcs/README.md). See [CONTRIBUTING.md](CONTRIBUTING.md), [GOVERNANCE.md](GOVERNANCE.md), and our [Code of Conduct](CODE_OF_CONDUCT.md).

Security issues in the specifications themselves: see [SECURITY.md](SECURITY.md).

## License and trademarks

The specifications, schemas, and all other content in this repository are licensed under [Apache License 2.0](LICENSE) — free to implement, royalty-free, with an express patent grant.

"Agent Governance Foundation", "AGF", and any AGF conformance marks are trademarks of the Agent Governance Foundation and are **not** covered by the content license. You may implement the specifications freely; claims of AGF conformance are governed by the [conformance process](conformance/README.md).
