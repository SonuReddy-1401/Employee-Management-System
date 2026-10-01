import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TARGETS = [
    {
        "name": "libs/common",
        "test_dir": "libs/common/tests",
        "cov_source": "libs/common/ems_common",
        "out_dir": "coverage_reports/libs_common",
        "min_overall": 80.0,
        "min_domain": None,
    },
    {
        "name": "services/auth",
        "test_dir": "services/auth/tests",
        "cov_source": "services/auth/app",
        "out_dir": "coverage_reports/services_auth",
        "min_overall": 0.0,
        "min_domain": 85.0,
    },
    {
        "name": "services/employee",
        "test_dir": "services/employee/tests",
        "cov_source": "services/employee/app",
        "out_dir": "coverage_reports/services_employee",
        "min_overall": 0.0,
        "min_domain": 85.0,
    },
    {
        "name": "services/leave",
        "test_dir": "services/leave/tests",
        "cov_source": "services/leave/app",
        "out_dir": "coverage_reports/services_leave",
        "min_overall": 0.0,
        "min_domain": 85.0,
    },
    {
        "name": "services/payroll",
        "test_dir": "services/payroll/tests",
        "cov_source": "services/payroll/app",
        "out_dir": "coverage_reports/services_payroll",
        "min_overall": 0.0,
        "min_domain": 85.0,
    },
    {
        "name": "services/notification",
        "test_dir": "services/notification/tests",
        "cov_source": "services/notification/app",
        "out_dir": "coverage_reports/services_notification",
        "min_overall": 0.0,
        "min_domain": 85.0,
    },
    {
        "name": "services/gateway",
        "test_dir": "services/gateway/tests",
        "cov_source": "services/gateway/app",
        "out_dir": "coverage_reports/services_gateway",
        "min_overall": 0.0,
        "min_domain": 85.0,
    },
]


def run_pytest_target(target):
    out_dir = Path(target["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    json_report = out_dir / "coverage.json"
    html_report = out_dir / "htmlcov"
    junit_report = out_dir / "junit.xml"

    env = os.environ.copy()
    env["PYTHONPATH"] = "."

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        target["test_dir"],
        f"--cov={target['cov_source']}",
        f"--cov-report=json:{json_report}",
        f"--cov-report=html:{html_report}",
        f"--junitxml={junit_report}",
        "-q",
    ]

    result = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    passed = 0
    failed = 0

    if junit_report.exists():
        try:
            tree = ET.parse(junit_report)
            root = tree.getroot()
            suites = list(root) if root.tag == "testsuites" else [root]
            for suite in suites:
                n_tests = int(suite.attrib.get("tests", 0))
                n_fail = int(suite.attrib.get("failures", 0))
                n_err = int(suite.attrib.get("errors", 0))
                failed += n_fail + n_err
                passed += n_tests - n_fail - n_err
        except Exception:
            pass

    overall_pct = 0.0
    domain_pct = None

    if json_report.exists():
        with open(json_report, "r", encoding="utf-8") as f:
            data = json.load(f)

        tot_stmts = data.get("totals", {}).get("num_statements", 0)
        tot_cov = data.get("totals", {}).get("covered_lines", 0)
        overall_pct = (tot_cov / tot_stmts * 100.0) if tot_stmts > 0 else 0.0

        dom_stmts = 0
        dom_cov = 0
        for file_path, file_data in data.get("files", {}).items():
            norm_path = file_path.replace("\\", "/")
            if "/app/domain/" in norm_path:
                summary = file_data.get("summary", {})
                dom_stmts += summary.get("num_statements", 0)
                dom_cov += summary.get("covered_lines", 0)

        if dom_stmts > 0:
            domain_pct = dom_cov / dom_stmts * 100.0
        elif target["min_domain"] is not None:
            domain_pct = 100.0

    target_ok = True
    if failed > 0:
        target_ok = False
    if target["min_overall"] > 0 and overall_pct < target["min_overall"]:
        target_ok = False
    if target["min_domain"] is not None and (domain_pct is None or domain_pct < target["min_domain"]):
        target_ok = False

    return {
        "name": target["name"],
        "overall_pct": overall_pct,
        "domain_pct": domain_pct,
        "passed": passed,
        "failed": failed,
        "ok": target_ok,
    }


def main():
    results = []
    all_ok = True

    for target in TARGETS:
        res = run_pytest_target(target)
        results.append(res)
        if not res["ok"]:
            all_ok = False

    # Format Table
    header = "| Target | Overall % | Domain % | Passed | Failed | Status |"
    divider = "| :--- | :--- | :--- | :--- | :--- | :--- |"
    rows = []

    for r in results:
        overall_str = f"{r['overall_pct']:.1f}%"
        domain_str = f"{r['domain_pct']:.1f}%" if r["domain_pct"] is not None else "N/A"
        status_str = "PASSED" if r["ok"] else "FAILED"
        rows.append(f"| {r['name']} | {overall_str} | {domain_str} | {r['passed']} | {r['failed']} | {status_str} |")

    table_md = "\n".join([header, divider] + rows)

    print(table_md)

    # Write to docs/COVERAGE.md
    docs_dir = Path("docs")
    docs_dir.mkdir(parents=True, exist_ok=True)
    with open(docs_dir / "COVERAGE.md", "w", encoding="utf-8") as f:
        f.write("# Coverage Audit Report\n\n")
        f.write(table_md + "\n")

    if not all_ok:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
