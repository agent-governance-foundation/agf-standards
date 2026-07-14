# RFCs — Requests for Comments

Substantive changes to the AGF specifications go through this process. "Substantive" means anything that changes normative behavior: MUST/SHOULD/MAY statements, wire formats, algorithms, error codes, or interoperability requirements. New specifications also start here.

Editorial fixes don't need an RFC — open a pull request directly.

## Process

1. **Copy the template**: `cp 0000-template.md 0000-my-proposal.md` (keep `0000` for now; the number is assigned at merge).
2. **Fill it in** and open a pull request. The PR is the discussion venue.
3. **Discussion period**: minimum 14 days for changes to existing specs, and the discussion stays open as long as it's productive. Maintainers may invite specific implementers to weigh in.
4. **Final comment period**: when discussion converges, a maintainer proposes a disposition (accept / reject / postpone) and opens a 7-day final comment period, announced on the PR.
5. **Decision**: a maintainer records the disposition on the PR. Accepted RFCs are assigned the next number, merged into this directory, and linked from the implementing spec change. Rejected and postponed RFCs are closed with the reasoning recorded.

An accepted RFC is a decision, not a spec change by itself — the spec edits land in a follow-up PR that links back to the RFC and bumps the spec's version per [GOVERNANCE.md](../GOVERNANCE.md).

## Index

| RFC | Title | Status |
|---|---|---|
| [0001](0001-aap-core-kernel.md) | AAP-Core — a normative kernel for the Agent Authorization Protocol | Draft |
