# CLAUDE.md

Public, vendor-neutral specification for the Agent Authorization Protocol (AAP), Apache 2.0.

## Layout
- `specs/` — kernel + numbered specifications (normative text)
- `schemas/` — JSON Schema / OpenAPI
- `conformance/` — conformance suite and scenarios
- `adoption/`, `rfcs/` — adoption guidance and proposals
- Top level: `README.md`, `GOVERNANCE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `authorization-flow.md`, `vision-and-mission.md`

## Rules
- This repo is **public**. Anything committed or pushed is world-readable, including commit messages. Keep wording
  vendor-neutral: no internal record ids, no private repo or product names.
- Version numbers are independent of any other repo's. Bump only with a real normative edit; diff the prose before
  calling a spec stale.
- A spec edit here must be mirrored in the private working copy of the specs, and vice versa. Flag implementations
  that may fall out of contract rather than changing them silently.
- Verify `origin/main` before calling anything published. Do not push or merge local draft branches.
- Indexes and summaries link to the spec; they never copy normative text.
