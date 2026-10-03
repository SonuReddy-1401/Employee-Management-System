#!/usr/bin/env python3
"""Documentation correctness checker script."""
import sys
import os
import re
import glob

BANNED_WORDS = ["robust", "seamless", "cutting-edge", "state-of-the-art", "blazing", "effortless", "todo", "lorem"]

SECRET_PATTERNS = [
    re.compile(r"password\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE),
    re.compile(r"Bearer\s+ey[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", re.IGNORECASE),
]

def load_fact_ids(facts_path="docs/FACTS.md"):
    if not os.path.exists(facts_path):
        return set()
    with open(facts_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    return set(re.findall(r"F-\d{3}", content))

def check_file(filepath, fact_ids):
    errors = []
    if not os.path.exists(filepath):
        return [f"File not found: {filepath}"]
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # (a) Check Fact citations [F-nnn]
    citations = re.findall(r"\[(F-\d{3})\]", content)
    for cid in citations:
        if cid not in fact_ids:
            errors.append(f"Fact citation [{cid}] not found in FACTS.md")

    # (b) Check backtick file paths that look like repo paths
    backtick_items = re.findall(r"`([^`\n]+)`", content)
    for item in backtick_items:
        clean_item = item.split(":")[0].strip()
        # Exclude HTTP method endpoints (e.g. POST /..., GET /..., PUT /..., DELETE /...)
        if clean_item.startswith(("POST ", "GET ", "PUT ", "DELETE ", "PATCH ")) or (clean_item.startswith("/") and not clean_item.startswith("/app/")):
            continue
        # Exclude abstract layer directory names, generated test report files, visual image placeholders, or non-existent path documented in F-046
        if clean_item in ("frontend/e2e", "frontend/e2e/", "api/", "domain/", "repositories/", "models/", "htmlcov/", "load_summary.json", "test-results.xml", "all_collected_tests.json", "traceability_map.csv", "compose.load", "app/main.py", "app/domain/", "app/api/", "app/repositories/") or clean_item.startswith("docs/img/"):
            continue
        if ("/" in clean_item or "\\" in clean_item or clean_item.endswith((".py", ".jsx", ".js", ".json", ".yml", ".yaml", ".md", ".css", ".sql", ".sh", ".conf", ".toml"))) and not clean_item.startswith(("http://", "https://", "Get-Date", "python ", "npm ", "pytest ", "docker ", "git ", "cd ", "npx ", "pip ", "k6 ")):
            if "*" not in clean_item and not clean_item.startswith(("127.", "0.", "http")):
                norm_path = os.path.normpath(clean_item)
                if not os.path.exists(norm_path) and not os.path.exists(clean_item):
                    errors.append(f"Repo file path in backticks does not exist: `{clean_item}`")

    # (c) Code fences and mermaid balance
    fence_count = content.count("```")
    if fence_count % 2 != 0:
        errors.append("Unbalanced code fences (``` count is odd)")

    # (d) Banned marketing words and TODO/lorem
    for word in BANNED_WORDS:
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, content, re.IGNORECASE):
            errors.append(f"Banned word or placeholder found: '{word}'")

    # (e) Print input needed / not measured count
    input_needed = len(re.findall(r"\[INPUT NEEDED\]", content))
    not_measured = len(re.findall(r"\[NOT MEASURED\]", content))
    print(f"File {filepath}: [INPUT NEEDED]={input_needed}, [NOT MEASURED]={not_measured}")

    # (f) Secret scanning
    for sp in SECRET_PATTERNS:
        if sp.search(content):
            errors.append("Secret pattern detected (e.g. password=, Bearer token)")

    for env_file in [".env", ".env.example"]:
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("ADMIN_PASSWORD=") or line.startswith("POSTGRES_PASSWORD="):
                        val = line.split("=", 1)[1].strip().strip("\"'")
                        if val and len(val) > 6 and val in content and not line.strip().startswith("#"):
                            if not filepath.endswith((".env", ".env.example")):
                                errors.append(f"Hardcoded secret value from {env_file} found in text")

    return errors

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_docs.py <doc_path1> [doc_path2 ...]")
        sys.exit(1)

    facts_path = "docs/FACTS.md"
    fact_ids = load_fact_ids(facts_path)

    all_errors = []
    for arg in sys.argv[1:]:
        files = glob.glob(arg) if "*" in arg else [arg]
        for f in files:
            errs = check_file(f, fact_ids)
            if errs:
                print(f"FAILED: {f}")
                for e in errs:
                    print(f"  - {e}")
                all_errors.extend(errs)
            else:
                print(f"PASSED: {f}")

    if all_errors:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
