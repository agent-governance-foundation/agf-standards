#!/usr/bin/env python3
"""Validate kernel/fixtures/*.json against kernel/*.schema.json.

Usage: python3 check.py   (run from the schemas/kernel directory,
       or python3 schemas/kernel/check.py from the repo root)
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

SCHEMA_NAMES = ["actor", "authority", "action", "decision", "receipt", "invalidation"]

# Fixtures that don't follow the <schema>.valid/invalid.json convention.
OVERRIDES = {
    "kernel-neg-05.flagged.json": "receipt",
    "kernel-neg-05.decision.json": "decision",
}

# Spec 00 §3.2 — the normative field mapping from AGF's JWT wire format
# (Spec 01 delegation token) to the kernel abstract-model field names used
# by authority.schema.json. Both are the reference serialization and the
# canonical shape; this table is what "conforms to" means between them.
JWT_TO_AUTHORITY_FIELD_MAP = {
    "jti": "id",
    "iss": "grantor",
    "sub": "grantee",
    "scope": "scope",
    "iat": "issued_at",
    "exp": "expires_at",
    "parent": "parent",
    "constraints": "constraints",
    "policy_version": "policy_ref",
}

# authority-jwt.*.json fixtures don't validate directly against a single
# schema file the way the others do — see check_authority_jwt_fixture().
AUTHORITY_JWT_PREFIX = "authority-jwt."


def map_jwt_claims_to_authority(claims):
    """Apply the Spec 00 §3.2 field mapping. Only maps keys present in
    `claims` — a claim's absence (e.g. no `parent` on a root token) is
    preserved as absence, not synthesized.
    """
    return {
        JWT_TO_AUTHORITY_FIELD_MAP[k]: v
        for k, v in claims.items()
        if k in JWT_TO_AUTHORITY_FIELD_MAP
    }


def check_authority_jwt_fixture(path, authority_schema):
    """Two checks, both must hold for a `.valid.` fixture: mapping fidelity
    (applying the Spec 00 §3.2 table to jwt_claims reproduces kernel_mapped
    exactly) and structural conformance (the mapped result validates against
    authority.schema.json). A fixture can be individually schema-valid yet
    still fail mapping fidelity — that's the case authority-jwt.invalid.json
    exercises, and schema validation alone would miss it.
    """
    import jsonschema  # local import: only called once main() has confirmed it's installed

    with open(path) as f:
        doc = json.load(f)
    computed = map_jwt_claims_to_authority(doc["jwt_claims"])
    mapping_ok = computed == doc["kernel_mapped"]
    schema_errors = list(jsonschema.Draft202012Validator(authority_schema).iter_errors(doc["kernel_mapped"]))
    structurally_ok = len(schema_errors) == 0
    return mapping_ok and structurally_ok


def schema_for(fixture_path):
    name = fixture_path.name
    if name in OVERRIDES:
        return OVERRIDES[name]
    for schema_name in SCHEMA_NAMES:
        if name.startswith(schema_name + "."):
            return schema_name
    return None


def expect_valid(fixture_path):
    name = fixture_path.name
    if name in OVERRIDES:
        return True
    return ".valid." in name


def main():
    fixture_files = sorted(FIXTURES.glob("*.json"))
    if not fixture_files:
        print(f"No fixtures found under {FIXTURES}")
        return 1

    for path in fixture_files:
        with open(path) as f:
            json.load(f)  # well-formedness check always runs

    try:
        import jsonschema
    except ImportError:
        print("jsonschema not installed — ran JSON well-formedness check only.")
        print(f"All {len(fixture_files)} fixture files are well-formed JSON.")
        return 0

    with open(HERE / "authority.schema.json") as f:
        authority_schema = json.load(f)

    failures = []
    for path in fixture_files:
        if path.name.startswith(AUTHORITY_JWT_PREFIX):
            should_be_valid = expect_valid(path)
            is_valid = check_authority_jwt_fixture(path, authority_schema)
            if is_valid != should_be_valid:
                want = "valid" if should_be_valid else "invalid"
                got = "valid" if is_valid else "invalid"
                failures.append(f"{path.name}: expected {want}, got {got}")
            else:
                print(f"OK  {path.name} (authority-jwt mapping, {'valid' if is_valid else 'invalid'} as expected)")
            continue

        schema_name = schema_for(path)
        if schema_name is None:
            failures.append(f"{path.name}: no schema mapping found")
            continue
        schema_path = HERE / f"{schema_name}.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)
        with open(path) as f:
            instance = json.load(f)

        should_be_valid = expect_valid(path)
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(instance))
        is_valid = len(errors) == 0

        if is_valid != should_be_valid:
            want = "valid" if should_be_valid else "invalid"
            got = "valid" if is_valid else "invalid"
            failures.append(f"{path.name}: expected {want}, got {got}")
        else:
            print(f"OK  {path.name} ({schema_name}, {'valid' if is_valid else 'invalid'} as expected)")

    if failures:
        print("\nFAILURES:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print(f"\nAll {len(fixture_files)} fixtures validated as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
