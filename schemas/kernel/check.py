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

    failures = []
    for path in fixture_files:
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
