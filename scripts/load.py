import os
import sys
import time
import json
import base64
import subprocess
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.load_verify import expected_from_summary, compare

# Environment & Credential Check
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
RABBITMQ_USER = os.getenv("RABBITMQ_MGMT_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_MGMT_PASSWORD")
RABBITMQ_MGMT_URL = os.getenv("RABBITMQ_MGMT_URL", "http://localhost:15672").rstrip("/")

LEAVE_DB_USER = os.getenv("LEAVE_DB_USER", "leave_user")
LEAVE_DB_NAME = os.getenv("LEAVE_DB_NAME", "leave_db")
EMPLOYEE_DB_USER = os.getenv("EMPLOYEE_DB_USER", "emp_user")
EMPLOYEE_DB_NAME = os.getenv("EMPLOYEE_DB_NAME", "employee_db")
AUTH_DB_USER = os.getenv("AUTH_DB_USER", "auth_user")
AUTH_DB_NAME = os.getenv("AUTH_DB_NAME", "auth_db")
PAYROLL_DB_USER = os.getenv("PAYROLL_DB_USER", "payroll_user")
PAYROLL_DB_NAME = os.getenv("PAYROLL_DB_NAME", "payroll_db")
NOTIFICATION_DB_USER = os.getenv("NOTIFICATION_DB_USER", "notification_user")
NOTIFICATION_DB_NAME = os.getenv("NOTIFICATION_DB_NAME", "notification_db")

missing = []
if not ADMIN_EMAIL:
    missing.append("ADMIN_EMAIL")
if not ADMIN_PASSWORD:
    missing.append("ADMIN_PASSWORD")
if not RABBITMQ_USER:
    missing.append("RABBITMQ_MGMT_USER")
if not RABBITMQ_PASS:
    missing.append("RABBITMQ_MGMT_PASSWORD")

if missing:
    print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
    sys.exit(1)


def run_cmd(cmd_list, capture=False):
    return subprocess.run(
        cmd_list, cwd=REPO_ROOT, stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None, text=True
    )


def check_health(url, timeout=5.0):
    try:
        req = urllib.request.Request(f"{url}/health")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def wait_service_healthy(name, url, timeout=60.0):
    start = time.time()
    while time.time() - start < timeout:
        if check_health(url):
            return True
        time.sleep(1.0)
    return False


def query_rabbitmq_queue(queue_name):
    url = f"{RABBITMQ_MGMT_URL}/api/queues/%2F/{queue_name}"
    auth_str = base64.b64encode(f"{RABBITMQ_USER}:{RABBITMQ_PASS}".encode("utf-8")).decode("utf-8")
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth_str}"})
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                ready = data.get("messages_ready", 0)
                unack = data.get("messages_unacknowledged", 0)
                return ready, unack
    except Exception:
        pass
    return None, None


def query_db_count(service_db, user, dbname, query):
    cmd = [
        "docker", "compose", "exec", "-T", service_db,
        "psql", "-U", user, "-d", dbname, "-tAc", query
    ]
    res = run_cmd(cmd, capture=True)
    if res.returncode == 0:
        try:
            return int(res.stdout.strip())
        except ValueError:
            pass
    return None


def get_all_db_counts():
    return {
        "leaves_approved": query_db_count("leave-db", LEAVE_DB_USER, LEAVE_DB_NAME, "select count(*) from leaves where status = 'APPROVED'"),
        "outbox_LeaveRequested": query_db_count("leave-db", LEAVE_DB_USER, LEAVE_DB_NAME, "select count(*) from outbox where event_type = 'LeaveRequested'"),
        "outbox_LeaveApproved": query_db_count("leave-db", LEAVE_DB_USER, LEAVE_DB_NAME, "select count(*) from outbox where event_type = 'LeaveApproved'"),
        "outbox_EmployeeOnboarded": query_db_count("employee-db", EMPLOYEE_DB_USER, EMPLOYEE_DB_NAME, "select count(*) from outbox where event_type = 'EmployeeOnboarded'"),
        "employees_active": query_db_count("employee-db", EMPLOYEE_DB_USER, EMPLOYEE_DB_NAME, "select count(*) from employees where status = 'ACTIVE'"),
        "employees_non_active": query_db_count("employee-db", EMPLOYEE_DB_USER, EMPLOYEE_DB_NAME, "select count(*) from employees where status != 'ACTIVE'"),
        "auth_users": query_db_count("auth-db", AUTH_DB_USER, AUTH_DB_NAME, "select count(*) from users"),
        "payroll_profiles": query_db_count("payroll-db", PAYROLL_DB_USER, PAYROLL_DB_NAME, "select count(*) from payroll_profiles"),
        "payroll_leave_deductions": query_db_count("payroll-db", PAYROLL_DB_USER, PAYROLL_DB_NAME, "select count(*) from leave_deductions"),
        "notifications_LeaveRequested": query_db_count("notification-db", NOTIFICATION_DB_USER, NOTIFICATION_DB_NAME, "select count(*) from notifications where event_type = 'LeaveRequested'"),
        "notifications_LeaveApproved": query_db_count("notification-db", NOTIFICATION_DB_USER, NOTIFICATION_DB_NAME, "select count(*) from notifications where event_type = 'LeaveApproved'"),
        "notifications_EmployeeOnboarded": query_db_count("notification-db", NOTIFICATION_DB_USER, NOTIFICATION_DB_NAME, "select count(*) from notifications where event_type = 'EmployeeOnboarded'"),
        "notifications_total": query_db_count("notification-db", NOTIFICATION_DB_USER, NOTIFICATION_DB_NAME, "select count(*) from notifications"),
        "notifications_distinct": query_db_count("notification-db", NOTIFICATION_DB_USER, NOTIFICATION_DB_NAME, "select count(distinct event_id) from notifications"),
    }


def main():
    print("==================== STARTING LOAD TEST ORCHESTRATION ====================")

    # Service health check
    services = {
        "Gateway": "http://localhost:8000",
        "Auth": "http://localhost:8001",
        "Employee": "http://localhost:8002",
        "Leave": "http://localhost:8003",
        "Payroll": "http://localhost:8004",
        "Notification": "http://localhost:8005",
    }
    for name, url in services.items():
        if not check_health(url):
            print(f"ERROR: Service {name} at {url} is not healthy! Start stack first.")
            sys.exit(1)

    k6_failed = False
    consistency_failed = False

    try:
        # Take Baseline DB Counts BEFORE starting k6
        print("Taking baseline DB record counts...")
        baseline_counts = get_all_db_counts()
        print("Baseline DB counts captured successfully.")

        # Recreate Gateway with high limits
        print("Recreating Gateway with high rate limits (docker-compose.load.yml)...")
        up_res = run_cmd(["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml", "-f", "docker-compose.load.yml", "up", "-d", "gateway"])
        if up_res.returncode != 0:
            print("ERROR: Failed to recreate gateway with load override.")
            sys.exit(1)

        if not wait_service_healthy("Gateway", "http://localhost:8000", timeout=60.0):
            print("ERROR: Gateway failed to become healthy after applying load override.")
            sys.exit(1)
        print("Gateway rate limits overridden successfully.")

        # Run k6 in Docker
        load_dir = REPO_ROOT / "tests" / "load"
        results_dir = load_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        k6_image = os.getenv("LOAD_K6_IMAGE", "grafana/k6:2.3.0")
        read_max_vus = os.getenv("LOAD_READ_MAX_VUS", "30")
        leave_max_vus_val = int(os.getenv("LOAD_LEAVE_MAX_VUS", "15"))
        onboard_rate = os.getenv("LOAD_ONBOARD_RATE", "2")

        cmd = [
            "docker", "run", "--rm", "-i",
            "-v", f"{load_dir.as_posix()}:/scripts",
            "-e", "BASE_URL=http://host.docker.internal:8000",
            "-e", f"ADMIN_EMAIL={ADMIN_EMAIL}",
            "-e", f"ADMIN_PASSWORD={ADMIN_PASSWORD}",
            "-e", f"READ_MAX_VUS={read_max_vus}",
            "-e", f"LEAVE_MAX_VUS={leave_max_vus_val}",
            "-e", f"ONBOARD_RATE={onboard_rate}",
            k6_image,
            "run", "/scripts/ems.js"
        ]

        print(f"Executing k6 load test using image {k6_image}...")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()

        proc.wait()
        if proc.returncode != 0:
            print(f"\n[K6 RESULT] k6 process returned exit code {proc.returncode} (Thresholds failed).")
            k6_failed = True
        else:
            print("\n[K6 RESULT] k6 execution completed successfully.")

        # Post-run queue and outbox consistency checks
        print("\n==================== POST-RUN CONSISTENCY CHECKS ====================")
        max_drain_timeout = 120.0
        poll_interval = 2.0

        checks_spec = [
            ("Payroll Queue Drained", "queue", "ems.payroll.queue"),
            ("Notification Queue Drained", "queue", "ems.notification.queue"),
            ("Payroll DLQ Empty", "queue", "ems.payroll.dlq"),
            ("Notification DLQ Empty", "queue", "ems.notification.dlq"),
            ("Leave Outbox Empty", "outbox", ("leave-db", LEAVE_DB_USER, LEAVE_DB_NAME)),
            ("Employee Outbox Empty", "outbox", ("employee-db", EMPLOYEE_DB_USER, EMPLOYEE_DB_NAME)),
        ]

        for check_name, ctype, params in checks_spec:
            start_t = time.time()
            passed = False
            last_val = None

            while time.time() - start_t <= max_drain_timeout:
                if ctype == "queue":
                    ready, unack = query_rabbitmq_queue(params)
                    if ready is not None and unack is not None:
                        last_val = f"ready={ready}, unack={unack}"
                        if ready == 0 and unack == 0:
                            passed = True
                            break
                elif ctype == "outbox":
                    service_db, u, dbn = params
                    cnt = query_db_count(service_db, u, dbn, "select count(*) from outbox where published_at is null")
                    if cnt is not None:
                        last_val = f"unpublished={cnt}"
                        if cnt == 0:
                            passed = True
                            break
                time.sleep(poll_interval)

            elapsed = time.time() - start_t
            status_str = "PASS" if passed else "FAIL"
            if not passed:
                consistency_failed = True
            print(f"[{status_str}] {check_name}: {last_val} (took {elapsed:.2f}s)")

        # Database Row-Count Verification against k6 Summary
        print("\n==================== DATABASE ROW-COUNT VERIFICATION ====================")
        summary_path = results_dir / "summary.json"
        if not summary_path.exists():
            print("ERROR: summary.json not found! Cannot verify DB counts.")
            consistency_failed = True
        else:
            with open(summary_path) as f:
                summary_data = json.load(f)

            expected_deltas = expected_from_summary(summary_data, setup_employees=leave_max_vus_val)

            db_poll_timeout = 180.0
            db_poll_start = time.time()
            final_actual_deltas = {}
            convergence_times = {}
            converged_keys = set()

            while time.time() - db_poll_start <= db_poll_timeout:
                current_counts = get_all_db_counts()
                now_t = time.time() - db_poll_start

                for key, exp_v in expected_deltas.items():
                    act_v = current_counts.get(key, 0) - baseline_counts.get(key, 0)
                    final_actual_deltas[key] = act_v
                    if act_v == exp_v and key not in converged_keys:
                        converged_keys.add(key)
                        convergence_times[key] = now_t

                if len(converged_keys) == len(expected_deltas):
                    break
                time.sleep(poll_interval)

            comparison_results = compare(expected_deltas, final_actual_deltas)

            # Check notification duplicates
            curr_notif_tot = current_counts.get("notifications_total", 0) - baseline_counts.get("notifications_total", 0)
            curr_notif_dist = current_counts.get("notifications_distinct", 0) - baseline_counts.get("notifications_distinct", 0)
            no_duplicates = (curr_notif_tot == curr_notif_dist)

            # Check non-ACTIVE employee increase
            non_active_delta = current_counts.get("employees_non_active", 0) - baseline_counts.get("employees_non_active", 0)
            no_non_active_increase = (non_active_delta == 0)

            print(f"{'Check Name':<35} | {'Expected':<10} | {'Actual Delta':<12} | {'Status':<6} | {'Convergence Time'}")
            print("-" * 80)
            all_db_checks_ok = True
            for key, exp_v, act_v, ok in comparison_results:
                if not ok:
                    all_db_checks_ok = False
                c_time = f"{convergence_times.get(key, db_poll_timeout):.2f}s" if ok else "N/A"
                print(f"{key:<35} | {exp_v:<10} | {act_v:<12} | {'PASS' if ok else 'FAIL':<6} | {c_time}")

            # Print duplicate & non-active checks
            print("-" * 80)
            print(f"{'notifications_no_duplicates':<35} | {curr_notif_tot:<10} | {curr_notif_dist:<12} | {'PASS' if no_duplicates else 'FAIL':<6} | 0.00s")
            print(f"{'employees_non_active_unchanged':<35} | {0:<10} | {non_active_delta:<12} | {'PASS' if no_non_active_increase else 'FAIL':<6} | 0.00s")

            if not all_db_checks_ok or not no_duplicates or not no_non_active_increase:
                consistency_failed = True

        # Check docker compose ps status
        print("\n==================== DOCKER STACK STATUS CHECK ====================")
        ps_res = run_cmd(["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml", "ps"], capture=True)
        print(ps_res.stdout)
        if "unhealthy" in ps_res.stdout.lower() or "restarting" in ps_res.stdout.lower():
            print("ERROR: Container stack has unhealthy or restarting services!")
            consistency_failed = True

    finally:
        # ALWAYS restore default gateway
        print("\nRestoring default Gateway limits (docker-compose.yml + docker-compose.dev.yml)...")
        run_cmd(["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml", "up", "-d", "gateway"])
        wait_service_healthy("Gateway", "http://localhost:8000", timeout=60.0)
        print("Default Gateway restored.")

    # Verdict
    print("\n==================== FINAL VERDICT ====================")
    if k6_failed or consistency_failed:
        print("FINAL VERDICT: LOAD TEST FAILED (Thresholds or consistency checks failed).")
        sys.exit(1)
    else:
        print("FINAL VERDICT: LOAD TEST PASSED (All thresholds and consistency checks passed).")
        sys.exit(0)


if __name__ == "__main__":
    main()
