#!/usr/bin/env python3
"""Validate the Core-format schemas in this directory against fixtures/.

For each <name>.schema.json here:
  fixtures/<name>.valid*.json    MUST validate
  fixtures/<name>.invalid*.json  MUST NOT validate

Also re-derives the Spec 07 §11.2 / Spec 25 §2.2 test vectors in
fixtures/signed-evidence.vectors.json (canonical bytes, SHA-256, salted
HMAC-SHA256), and evaluates the Spec 07 §11.8 revocation classification cases in
fixtures/signed-evidence.revocation-cases.json against a reference classifier.

Exits non-zero if jsonschema is not installed, or if either required data file
is missing: a check that could not run is a failure, never a pass.

Usage: python3 schemas/check.py   (from the repo root, or from schemas/)
Kernel schemas have their own checker: schemas/kernel/check.py.
"""
import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
MAX_INT = 2 ** 53 - 1


def c14n_1_1(obj) -> bytes:
    """AGF-C14N-1.1 (Spec 25 §2.2): sorted keys, compact separators, ASCII
    output with \\uXXXX escapes, no floats, integers within ±(2^53 − 1)."""
    def walk(o):
        if isinstance(o, float):
            raise TypeError("AGF-C14N-1.1: float not permitted")
        if isinstance(o, bool) or o is None or isinstance(o, str):
            return
        if isinstance(o, int):
            if abs(o) > MAX_INT:
                raise ValueError("AGF-C14N-1.1: integer out of range")
            return
        if isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        else:
            raise TypeError(f"AGF-C14N-1.1: unsupported type {type(o).__name__}")
    walk(obj)
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=True).encode("utf-8")


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


REQUIRED_DATA = ["signed-evidence.vectors.json", "signed-evidence.revocation-cases.json"]


def classify_revocation(decision_ts: int, invalidations: list[dict]) -> tuple[str, str]:
    """Reference for Spec 07 §11.8's revocation table, for one jti. Each
    Invalidation is assumed verified and bound to the verifying organisation."""
    pre = [i for i in invalidations if i["occurred_at"] < decision_ts]
    if any(i["detected_at"] <= decision_ts for i in pre):
        return "violation", "PARENT_REVOKED"
    if pre:
        return "violation", "REVOCATION_DETECTED_AFTER_DECISION"
    if invalidations:
        return "verified", "REVOKED_AFTER_DECISION"
    return "not_established", "REVOCATION_STATUS_UNESTABLISHED"


def check_revocation_cases() -> list[str]:
    errors = []
    data = json.loads((FIXTURES / "signed-evidence.revocation-cases.json").read_text(encoding="utf-8"))
    for c in data["cases"]:
        got = classify_revocation(data["decision_ts"], c["invalidations"])
        want = (c["expected"]["status"], c["expected"]["code"])
        if got != want:
            errors.append(f"revocation case '{c['name']}': expected {want}, reference gives {got}")
        else:
            print(f"OK  revocation case: {c['name']} -> {got[0]} {got[1]}")
    return errors


def check_vectors() -> list[str]:
    errors = []
    path = FIXTURES / "signed-evidence.vectors.json"
    v = json.loads(path.read_text(encoding="utf-8"))
    for i, d in enumerate(v["salted_digests"]):
        got = b64u(hmac.new(b64u_decode(d["salt_b64url"]), d["input_utf8"].encode("utf-8"), hashlib.sha256).digest())
        if got != d["expected"]:
            errors.append(f"salted_digests[{i}]: expected {d['expected']}, derived {got}")
    for i, c in enumerate(v["canonicalization"]):
        b = c14n_1_1(c["input"])
        if b.decode("ascii") != c["expected_ascii"]:
            errors.append(f"canonicalization[{i}]: canonical form differs")
        if b64u(hashlib.sha256(b).digest()) != c["expected_sha256_b64url"]:
            errors.append(f"canonicalization[{i}]: sha256 differs")
    r = v["request_record_digest"]
    got = b64u(hashlib.sha256(c14n_1_1(r["approval_request_payload"])).digest())
    if got != r["expected"]:
        errors.append(f"request_record_digest: expected {r['expected']}, derived {got}")
    # Out-of-range integers must be rejected by 1.1.
    try:
        c14n_1_1({"n": MAX_INT + 1})
        errors.append("canonicalization: integer above 2^53-1 was not rejected")
    except ValueError:
        pass
    return errors


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        print("FAIL: jsonschema is not installed, so no schema was validated. "
              "Install it (pip install jsonschema) and re-run.")
        return 2

    missing = [n for n in REQUIRED_DATA if not (FIXTURES / n).exists()]
    if missing:
        print(f"FAIL: required data file(s) missing: {', '.join(missing)}")
        return 2

    failures = 0
    for schema_path in sorted(HERE.glob("*.schema.json")):
        name = schema_path.name[: -len(".schema.json")]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        fixtures = sorted(FIXTURES.glob(f"{name}.valid*.json")) + sorted(FIXTURES.glob(f"{name}.invalid*.json"))
        if not any(f.name.startswith(f"{name}.valid") for f in fixtures):
            print(f"FAIL {name}: no valid fixture")
            failures += 1
        for f in fixtures:
            doc = json.loads(f.read_text(encoding="utf-8"))
            expect_valid = f.name.startswith(f"{name}.valid")
            errs = list(jsonschema.Draft202012Validator(schema).iter_errors(doc))
            ok = (not errs) if expect_valid else bool(errs)
            status = "valid" if expect_valid else "invalid"
            print(f"{'OK ' if ok else 'FAIL'} {f.name} ({name}, {status} as expected)" if ok
                  else f"FAIL {f.name} ({name}): expected {status}; errors={[e.message for e in errs][:2]}")
            failures += 0 if ok else 1

    for e in check_vectors() + check_revocation_cases():
        print(f"FAIL {e}")
        failures += 1
    if failures:
        print(f"\n{failures} failure(s).")
        return 1
    print("\nAll Core-format fixtures, test vectors and revocation cases validated as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
