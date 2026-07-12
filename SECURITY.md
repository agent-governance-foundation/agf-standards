# Security Policy

## Scope

This repository contains **specifications**, not running software. A security issue here means a flaw in a specified protocol or format — for example:

- a token or chain-validation rule that permits privilege escalation or scope expansion
- a revocation design that leaves a window it claims to close
- a signature or canonicalization scheme vulnerable to substitution or malleability
- an audit format that can be forged or repudiated

Vulnerabilities in any particular **implementation** of these specs should be reported to that implementation's vendor or project, not here.

## Reporting

Please report specification-level security issues **privately** before any public disclosure:

- Use [GitHub private vulnerability reporting](../../security/advisories/new) on this repository, or
- Email **ramesh.k@navattech.com** with subject line `[AGF-SEC]`.

Include the spec number and section, the attack scenario (who does what, and what they gain), and any suggested fix.

## What to expect

- Acknowledgment within **3 business days**.
- An assessment and remediation plan within **14 days**.
- Coordinated disclosure: we ask for up to **90 days** to publish a corrected spec revision and notify known implementers before public disclosure. We will credit reporters in the advisory unless you ask otherwise.

Because a spec flaw affects every conformant implementation, fixes to Stable specs are published as security advisories alongside the spec revision, with explicit guidance for implementers.
