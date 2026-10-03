#!/usr/bin/env python3
"""Traceability matrix generator script."""
import sys
import os
import re
import csv
import json
import subprocess

def collect_pytest_tests(target, env_path=None):
    env = os.environ.copy()
    if env_path:
        env["PYTHONPATH"] = env_path
    else:
        env["PYTHONPATH"] = "."
    py_exec = os.path.abspath(".venv/Scripts/python.exe") if os.path.exists(".venv/Scripts/python.exe") else sys.executable
    cmd = [py_exec, "-m", "pytest", target, "--collect-only", "-q"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=os.path.abspath("."))
        return [line.strip() for line in res.stdout.splitlines() if "::" in line and not line.startswith("warning")]
    except Exception as e:
        print(f"Warning: failed collecting pytest tests for {target}: {e}")
        return []

def collect_vitest_tests():
    cmd = ["npx.cmd" if os.name == "nt" else "npx", "vitest", "list"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.abspath("frontend"))
        return [line.strip() for line in res.stdout.splitlines() if line.strip().startswith("src/test/")]
    except Exception as e:
        print(f"Warning: failed collecting vitest tests: {e}")
        return []

def load_requirements(req_file="docs/REQUIREMENTS.md"):
    if not os.path.exists(req_file):
        return {}
    with open(req_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Parse table rows | **R-001** | text | source |
    reqs = {}
    matches = re.findall(r"\|\s*\*\*(R-\d{3})\*\*\s*\|\s*([^|]+)\|\s*([^|]+)\|", content)
    for rid, text, source in matches:
        reqs[rid] = {
            "text": text.strip(),
            "source": source.strip()
        }
    return reqs

def load_mappings(map_file="docs/traceability_map.csv"):
    if not os.path.exists(map_file):
        return []
    mappings = []
    with open(map_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader, None)
        for row in reader:
            if len(row) >= 3:
                mappings.append({
                    "requirement_id": row[0].strip(),
                    "test_node_id": row[1].strip(),
                    "level": row[2].strip().lower()
                })
    return mappings

def main():
    pytest_targets = [
        ("libs/common", "libs/common"),
        ("services/auth", "services/auth"),
        ("services/employee", "services/employee"),
        ("services/leave", "services/leave"),
        ("services/payroll", "services/payroll"),
        ("services/notification", "services/notification"),
        ("tests/contract", "."),
        ("tests/e2e", "."),
        ("tests/chaos", "."),
        ("tests/load", ".")
    ]

    all_tests = set()
    for target, env_path in pytest_targets:
        collected = collect_pytest_tests(target, env_path)
        all_tests.update(collected)

    vitest_tests = collect_vitest_tests()
    all_tests.update(vitest_tests)

    print(f"Collected total {len(all_tests)} real tests across Pytest and Vitest.")

    requirements = load_requirements("docs/REQUIREMENTS.md")
    mappings = load_mappings("docs/traceability_map.csv")

    # Validate mapping test names
    invalid_mappings = []
    for m in mappings:
        if m["test_node_id"] not in all_tests:
            invalid_mappings.append(m)

    if invalid_mappings:
        print("ERROR: Mapped test node IDs not found in collected tests:")
        for inv in invalid_mappings:
            print(f"  - [{inv['requirement_id']}] {inv['test_node_id']} (Level: {inv['level']})")
        sys.exit(1)

    # Build requirement mapping tree
    req_levels = {rid: {"unit": [], "integration": [], "contract": [], "e2e": [], "chaos": [], "load": [], "ui": []} for rid in requirements}
    
    for m in mappings:
        rid = m["requirement_id"]
        lvl = m["level"]
        test_id = m["test_node_id"]
        if rid in req_levels and lvl in req_levels[rid]:
            req_levels[rid][lvl].append(test_id)

    gaps = []
    mapped_count = 0
    for rid, lvl_dict in req_levels.items():
        total_tests = sum(len(v) for v in lvl_dict.values())
        if total_tests == 0:
            gaps.append(rid)
        else:
            mapped_count += 1

    print(f"\nTraceability Summary: Total={len(requirements)}, Mapped={mapped_count}, GAPs={len(gaps)}")
    if gaps:
        print("Requirements marked as GAP:")
        for g in gaps:
            print(f"  - {g}: {requirements[g]['text']}")

    # Write docs/TRACEABILITY.md
    lines = []
    lines.append("# Requirements Traceability Matrix\n")
    lines.append("This document provides end-to-end traceability mapping each requirement from `docs/REQUIREMENTS.md` to automated test suites across all test pyramid levels.\n")
    lines.append("## Traceability Matrix Table\n")
    lines.append("| Requirement ID | Requirement Summary | Unit | Integration | Contract | E2E | Chaos | Load | UI | Total Tests |")
    lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for rid, info in requirements.items():
        lvls = req_levels[rid]
        u = len(lvls["unit"])
        i = len(lvls["integration"])
        c = len(lvls["contract"])
        e = len(lvls["e2e"])
        ch = len(lvls["chaos"])
        l = len(lvls["load"])
        ui = len(lvls["ui"])
        tot = u + i + c + e + ch + l + ui
        lines.append(f"| **{rid}** | {info['text']} | {u} | {i} | {c} | {e} | {ch} | {l} | {ui} | **{tot}** |")

    lines.append("\n## GAP Analysis\n")
    if gaps:
        lines.append("The following requirements currently have zero automated tests mapped and are identified as GAPs:\n")
        for g in gaps:
            lines.append(f"- **{g}**: {requirements[g]['text']} (Source: `{requirements[g]['source']}`)")
    else:
        lines.append("Zero GAPs identified. 100% of defined requirements have at least one automated test mapped across the test pyramid.\n")

    lines.append("\n## Summary Metrics\n")
    lines.append(f"- **Total Requirements Defined**: {len(requirements)} [R-001 through R-037]")
    lines.append(f"- **Total Mapped Requirements**: {mapped_count}")
    lines.append(f"- **Total GAP Requirements**: {len(gaps)}")
    lines.append(f"- **Total Test Mappings**: {len(mappings)}")

    with open("docs/TRACEABILITY.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("Successfully generated docs/TRACEABILITY.md")
    sys.exit(0)

if __name__ == "__main__":
    main()
