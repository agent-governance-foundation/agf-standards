# Contributing

Thank you for helping build open standards for AI agent governance.

## Ways to contribute

- **Report a problem in a spec** — ambiguity, contradiction, missing edge case, security concern: [open an issue](../../issues). Say which spec and section (e.g. "Spec 02 §3.5").
- **Editorial fixes** — typos, broken links, formatting, clearer non-normative wording: open a pull request directly.
- **Substantive changes** — anything that changes normative behavior (MUST/SHOULD/MAY statements, wire formats, algorithms): follow the [RFC process](rfcs/README.md). Substantive PRs without an accepted RFC will be converted to RFC discussions, not merged.
- **Implementation experience** — if you're implementing a spec, reports of what was ambiguous, underspecified, or impractical are among the most valuable contributions a standard can receive. File them as issues tagged `implementation-experience`.
- **Schemas and test vectors** — [schemas/](schemas/) and [conformance/](conformance/) are early; contributions that extract machine-readable artifacts from the prose specs are very welcome.

## Style rules for spec text

- Normative statements use [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) keywords: MUST, MUST NOT, SHOULD, SHOULD NOT, MAY — capitalized.
- Non-normative material (rationale, examples) should be clearly marked as such.
- Wire-format examples must be valid (parseable JSON, correct field names) — examples are the first thing implementers copy.
- Specs must stay vendor-neutral: no references to any particular product, hosted service, or internal system. Describe behavior, not implementations.

## Pull request checklist

1. One logical change per PR.
2. If the change is normative, link the accepted RFC.
3. Update the affected spec's changelog table (version bump per [GOVERNANCE.md](GOVERNANCE.md)).
4. Sign off your commits (`git commit -s`) — we use the [Developer Certificate of Origin](https://developercertificate.org/).

## Conduct

All participation is covered by our [Code of Conduct](CODE_OF_CONDUCT.md).

## License of contributions

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE), including its patent grant.
