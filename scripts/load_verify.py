def expected_from_summary(summary: dict, setup_employees: int) -> dict:
    root_group = summary.get("root_group", {})
    checks = root_group.get("checks", [])
    
    check_map = {}
    for c in checks:
        name = c.get("name")
        if name:
            check_map[name] = c.get("passes", 0)

    required_checks = ["create_leave status 201", "approve_leave status 200", "onboard_employee status 201"]
    for req in required_checks:
        if req not in check_map:
            raise ValueError(f"Check '{req}' not found in k6 summary.")

    leave_created = check_map["create_leave status 201"]
    leave_approved = check_map["approve_leave status 200"]
    onboarded_in_scenario = check_map["onboard_employee status 201"]

    total_onboarded = onboarded_in_scenario + setup_employees

    return {
        "leaves_approved": leave_approved,
        "outbox_LeaveRequested": leave_created,
        "outbox_LeaveApproved": leave_approved,
        "outbox_EmployeeOnboarded": total_onboarded,
        "employees_active": total_onboarded,
        "auth_users": total_onboarded,
        "payroll_profiles": total_onboarded,
        "payroll_leave_deductions": leave_approved,
        "notifications_LeaveRequested": leave_created,
        "notifications_LeaveApproved": leave_approved,
        "notifications_EmployeeOnboarded": total_onboarded,
    }


def compare(expected: dict, actual_delta: dict) -> list:
    rows = []
    for key, exp_val in expected.items():
        act_val = actual_delta.get(key, 0)
        ok = (exp_val == act_val)
        rows.append((key, exp_val, act_val, ok))
    return rows
