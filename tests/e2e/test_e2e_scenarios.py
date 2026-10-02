from datetime import date, timedelta
from decimal import Decimal
import pytest
from tests.e2e.helpers import (
    E2EClient,
    compute_payslip_deduction,
    first_monday,
    unique_email,
    wait_queue_drained,
    wait_until,
)


def test_full_leave_to_payroll_journey(admin_client, employee_factory):
    # 1. Create HR, MANAGER, and EMPLOYEE (whose manager is MANAGER)
    hr_emp = employee_factory(role="HR", name="HR User")
    mgr_emp = employee_factory(role="MANAGER", name="Manager User")
    emp_user = employee_factory(
        role="EMPLOYEE",
        name="Journey Employee",
        monthly_salary=23000.0,
        manager_id=mgr_emp["id"],
    )

    hr_client = E2EClient()
    hr_client.login(hr_emp["email"], hr_emp["password"])

    mgr_client = E2EClient()
    mgr_client.login(mgr_emp["email"], mgr_emp["password"])

    emp_client = E2EClient()
    emp_client.login(emp_user["email"], emp_user["password"])

    try:
        # 2. Employee requests UNPAID leave for 3 consecutive weekdays starting on first Monday of March next year
        next_year = date.today().year + 1
        month = 3
        start_dt = first_monday(next_year, month)
        end_dt = start_dt + timedelta(days=2)  # Mon, Tue, Wed = 3 days

        req_res = emp_client.post(
            "/leaves",
            json={
                "employee_id": emp_user["id"],
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "leave_type": "UNPAID",
                "reason": "Family vacation",
            },
        )
        assert req_res.status_code == 201
        leave_id = req_res.json()["id"]
        assert req_res.json()["status"] == "PENDING"
        assert req_res.json()["days"] == 3

        # 3. Manager approves leave
        app_res = mgr_client.post(f"/leaves/{leave_id}/approve")
        assert app_res.status_code == 200
        assert app_res.json()["status"] == "APPROVED"

        # 4. Wait for employee notifications (EmployeeOnboarded, LeaveRequested, LeaveApproved)
        def check_notifications():
            r = emp_client.get(f"/notifications/{emp_user['id']}")
            if r.status_code == 200:
                types = {n["event_type"] for n in r.json()}
                return {"EmployeeOnboarded", "LeaveRequested", "LeaveApproved"}.issubset(types)
            return False

        wait_until(check_notifications, message="Notifications for onboarding and leave approval not received")

        # 5. Wait for queues to drain
        wait_queue_drained("ems.payroll.queue")
        wait_queue_drained("ems.notification.queue")

        # 6. HR runs payroll for March next year
        month_str = f"{next_year}-03"
        pay_res = hr_client.post(f"/payroll/run?month={month_str}")
        assert pay_res.status_code == 200

        # 7. Employee checks payslip
        slips_res = emp_client.get(f"/payslips/{emp_user['id']}")
        assert slips_res.status_code == 200
        slips = slips_res.json()
        matching_slips = [s for s in slips if s["month"] == month_str]
        assert len(matching_slips) == 1
        slip = matching_slips[0]

        expected_ded, expected_net = compute_payslip_deduction(23000.0, next_year, month, 3)

        assert float(slip["gross_salary"]) == 23000.0
        assert int(slip["unpaid_leave_days"]) == 3

        assert Decimal(str(slip["deduction"])) == expected_ded
        assert Decimal(str(slip["net_salary"])) == expected_net

    finally:
        hr_client.close()
        mgr_client.close()
        emp_client.close()


def test_cancelled_leave_removes_deduction(admin_client, employee_factory):
    mgr_emp = employee_factory(role="MANAGER", name="April Manager")
    emp_user = employee_factory(
        role="EMPLOYEE",
        name="Cancel Leave Employee",
        monthly_salary=18000.0,
        manager_id=mgr_emp["id"],
    )

    hr_emp = employee_factory(role="HR", name="April HR")

    hr_client = E2EClient()
    hr_client.login(hr_emp["email"], hr_emp["password"])

    mgr_client = E2EClient()
    mgr_client.login(mgr_emp["email"], mgr_emp["password"])

    emp_client = E2EClient()
    emp_client.login(emp_user["email"], emp_user["password"])

    try:


        next_year = date.today().year + 1
        month = 4
        start_dt = first_monday(next_year, month)
        end_dt = start_dt + timedelta(days=2)

        req_res = emp_client.post(
            "/leaves",
            json={
                "employee_id": emp_user["id"],
                "start_date": start_dt.isoformat(),
                "end_date": end_dt.isoformat(),
                "leave_type": "UNPAID",
                "reason": "Personal matters",
            },
        )
        assert req_res.status_code == 201




        leave_id = req_res.json()["id"]

        app_res = mgr_client.post(f"/leaves/{leave_id}/approve")
        assert app_res.status_code == 200

        canc_res = emp_client.post(f"/leaves/{leave_id}/cancel")
        assert canc_res.status_code == 200
        assert canc_res.json()["status"] == "CANCELLED"

        # Wait for LeaveCancelled notification
        def check_cancelled_notif():
            r = emp_client.get(f"/notifications/{emp_user['id']}")
            if r.status_code == 200:
                types = {n["event_type"] for n in r.json()}
                return "LeaveCancelled" in types
            return False

        wait_until(check_cancelled_notif, message="LeaveCancelled notification not received")

        # Wait for queues to drain
        wait_queue_drained("ems.payroll.queue")
        wait_queue_drained("ems.notification.queue")

        # HR runs payroll for April
        month_str = f"{next_year}-04"
        pay_res = hr_client.post(f"/payroll/run?month={month_str}")
        assert pay_res.status_code == 200

        # Employee reads payslip: 0 unpaid days, 0 deduction
        slips_res = emp_client.get(f"/payslips/{emp_user['id']}")
        assert slips_res.status_code == 200
        matching_slips = [s for s in slips_res.json() if s["month"] == month_str]
        assert len(matching_slips) == 1
        slip = matching_slips[0]

        assert slip["unpaid_leave_days"] == 0
        assert Decimal(str(slip["deduction"])) == Decimal("0.00")
        assert Decimal(str(slip["net_salary"])) == Decimal("18000.00")

    finally:
        hr_client.close()
        mgr_client.close()
        emp_client.close()


def test_permissions_through_gateway(admin_client, employee_factory):
    mgr1 = employee_factory(role="MANAGER", name="Manager 1")
    mgr2 = employee_factory(role="MANAGER", name="Manager 2")
    emp = employee_factory(role="EMPLOYEE", name="Perm Employee", manager_id=mgr1["id"])
    hr_emp = employee_factory(role="HR", name="Perm HR")

    emp_client = E2EClient()
    emp_client.login(emp["email"], emp["password"])

    mgr2_client = E2EClient()
    mgr2_client.login(mgr2["email"], mgr2["password"])

    hr_client = E2EClient()
    hr_client.login(hr_emp["email"], hr_emp["password"])

    try:

        # 1. EMPLOYEE cannot POST /employees (403)
        res1 = emp_client.post(
            "/employees",
            json={
                "name": "Forbidden Emp",
                "email": unique_email(),
                "department": "IT",
                "designation": "Dev",
                "initial_password": "Password123!",
                "monthly_salary": 4000.0,
            },
        )
        assert res1.status_code == 403

        # 2. EMPLOYEE cannot approve their own leave (403)
        next_year = date.today().year + 1
        start_dt = first_monday(next_year, 5)
        leave_res = emp_client.post(
            "/leaves",
            json={
                "employee_id": emp["id"],
                "start_date": start_dt.isoformat(),
                "end_date": (start_dt + timedelta(days=1)).isoformat(),
                "leave_type": "UNPAID",
                "reason": "Permissions testing",
            },
        )
        assert leave_res.status_code == 201




        leave_id = leave_res.json()["id"]

        own_app = emp_client.post(f"/leaves/{leave_id}/approve")
        assert own_app.status_code == 403

        # 3. MANAGER who is not employee's manager cannot approve (403)
        other_mgr_app = mgr2_client.post(f"/leaves/{leave_id}/approve")
        assert other_mgr_app.status_code == 403



        # 4. EMPLOYEE cannot read another employee's payslips (403) but HR can (200)
        emp_read = emp_client.get(f"/payslips/{mgr1['id']}")
        assert emp_read.status_code == 403

        hr_read = hr_client.get(f"/payslips/{emp['id']}")
        assert hr_read.status_code == 200

        # 5. No token on protected route gives 401
        anon_client = E2EClient()
        no_auth_res = anon_client.get("/employees")
        assert no_auth_res.status_code == 401
        anon_client.close()

        # 6. POST /internal/users through gateway gives 404
        internal_res = emp_client.post("/internal/users", json={"email": "hacker@test.com"})
        assert internal_res.status_code == 404

    finally:
        emp_client.close()
        mgr2_client.close()
        hr_client.close()


def test_duplicate_email_and_validation_through_gateway(admin_client, employee_factory):
    emp1 = employee_factory(role="EMPLOYEE", name="Validation User 1")

    # 1. Duplicate email gives 409
    dup_res = admin_client.post(
        "/employees",
        json={
            "name": "Validation User 2",
            "email": emp1["email"],
            "department": "HR",
            "designation": "Staff",
            "initial_password": "Password123!",
            "monthly_salary": 4000.0,
        },
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "CONFLICT"
    assert "message" in dup_res.json()["error"]

    # 2. Invalid body (missing required fields) gives 422
    bad_res = admin_client.post("/employees", json={"name": "Incomplete User"})
    assert bad_res.status_code == 422
    assert bad_res.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in bad_res.json()["error"]

    # 3. Unknown employee id gives 404
    fake_id = "00000000-0000-0000-0000-000000000000"
    missing_res = admin_client.get(f"/employees/{fake_id}")
    assert missing_res.status_code == 404
    assert missing_res.json()["error"]["code"] == "NOT_FOUND"
    assert "message" in missing_res.json()["error"]


def test_correlation_id_round_trip(admin_client):
    custom_cid = "e2e-correlation-id-999"

    res = admin_client.get("/employees", headers={"X-Correlation-ID": custom_cid})
    assert res.status_code == 200
    assert res.headers.get("x-correlation-id") == custom_cid

    res_no_cid = admin_client.get("/employees")
    assert res_no_cid.status_code == 200
    assert "x-correlation-id" in [k.lower() for k in res_no_cid.headers.keys()]


def test_onboarding_publishes_welcome_notification(admin_client, employee_factory):
    emp = employee_factory(role="EMPLOYEE", name="Welcome Employee")

    emp_client = E2EClient()
    emp_client.login(emp["email"], emp["password"])

    try:
        def check_welcome():
            r = emp_client.get(f"/notifications/{emp['id']}")
            if r.status_code == 200:
                notifs = r.json()
                welcome_notifs = [n for n in notifs if n.get("event_type") == "EmployeeOnboarded"]
                return len(welcome_notifs) == 1
            return False

        wait_until(check_welcome, message="Welcome notification not received or duplicated")

    finally:
        emp_client.close()
