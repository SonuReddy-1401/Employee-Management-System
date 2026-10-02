import pytest
from scripts.load_verify import expected_from_summary, compare


def test_expected_from_summary_success():
    sample_summary = {
        "root_group": {
            "checks": [
                {"name": "create_leave status 201", "passes": 50, "fails": 0},
                {"name": "approve_leave status 200", "passes": 45, "fails": 0},
                {"name": "onboard_employee status 201", "passes": 10, "fails": 0},
            ]
        }
    }
    setup_employees = 15
    expected = expected_from_summary(sample_summary, setup_employees)

    assert expected["leaves_approved"] == 45
    assert expected["outbox_LeaveRequested"] == 50
    assert expected["outbox_LeaveApproved"] == 45
    assert expected["outbox_EmployeeOnboarded"] == 25  # 10 + 15
    assert expected["employees_active"] == 25
    assert expected["auth_users"] == 25
    assert expected["payroll_profiles"] == 25
    assert expected["payroll_leave_deductions"] == 45
    assert expected["notifications_LeaveRequested"] == 50
    assert expected["notifications_LeaveApproved"] == 45
    assert expected["notifications_EmployeeOnboarded"] == 25


def test_expected_from_summary_missing_check_raises():
    incomplete_summary = {
        "root_group": {
            "checks": [
                {"name": "create_leave status 201", "passes": 50, "fails": 0},
            ]
        }
    }
    with pytest.raises(ValueError, match="Check 'approve_leave status 200' not found"):
        expected_from_summary(incomplete_summary, setup_employees=15)


def test_compare_matches_loss_and_duplicates():
    expected = {
        "metric_match": 10,
        "metric_loss": 10,
        "metric_duplicate": 10,
    }
    actual_delta = {
        "metric_match": 10,
        "metric_loss": 9,       # 1 loss
        "metric_duplicate": 11, # 1 duplicate
    }

    results = compare(expected, actual_delta)
    result_map = {row[0]: row for row in results}

    assert result_map["metric_match"] == ("metric_match", 10, 10, True)
    assert result_map["metric_loss"] == ("metric_loss", 10, 9, False)
    assert result_map["metric_duplicate"] == ("metric_duplicate", 10, 11, False)
