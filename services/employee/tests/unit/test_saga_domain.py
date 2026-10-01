import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from ems_common.errors import EMSError
from services.employee.app.domain.saga import OnboardingSaga
from services.employee.app.schemas.employee import EmployeeCreateRequest, EmployeeRole


@pytest.fixture
def mock_db():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_http_client():
    client = AsyncMock()
    return client


@pytest.fixture
def sample_payload():
    return EmployeeCreateRequest(
        name="Saga Unit Test User",
        email="saga.unit@example.com",
        department="Engineering",
        designation="Software Engineer",
        role=EmployeeRole.EMPLOYEE,
        initial_password="Password123!",
        monthly_salary=5000.0,
    )


@pytest.mark.asyncio
async def test_saga_happy_path(mock_db, mock_http_client, sample_payload):
    auth_resp = MagicMock(is_success=True)
    payroll_resp = MagicMock(is_success=True)
    mock_http_client.post.side_effect = [auth_resp, payroll_resp]

    saga = OnboardingSaga(mock_db, mock_http_client)
    emp = await saga.execute(sample_payload)

    assert emp.name == sample_payload.name
    assert emp.status == "ACTIVE"
    assert mock_http_client.post.call_count == 2
    assert mock_db.commit.call_count == 2


@pytest.mark.asyncio
async def test_saga_auth_non_success_response(mock_db, mock_http_client, sample_payload):
    auth_resp = MagicMock(is_success=False)
    mock_http_client.post.return_value = auth_resp

    saga = OnboardingSaga(mock_db, mock_http_client)

    with pytest.raises(EMSError) as exc_info:
        await saga.execute(sample_payload)

    assert exc_info.value.code == "ONBOARDING_FAILED"
    assert mock_http_client.post.call_count == 1
    assert mock_http_client.delete.call_count == 0


@pytest.mark.asyncio
async def test_saga_auth_exception(mock_db, mock_http_client, sample_payload):
    mock_http_client.post.side_effect = Exception("Auth network error")

    saga = OnboardingSaga(mock_db, mock_http_client)

    with pytest.raises(EMSError) as exc_info:
        await saga.execute(sample_payload)

    assert exc_info.value.code == "ONBOARDING_FAILED"
    assert mock_http_client.delete.call_count == 0


@pytest.mark.asyncio
async def test_saga_payroll_non_success_triggers_auth_compensation(mock_db, mock_http_client, sample_payload):
    auth_resp = MagicMock(is_success=True)
    payroll_resp = MagicMock(is_success=False)
    mock_http_client.post.side_effect = [auth_resp, payroll_resp]
    mock_http_client.delete.return_value = MagicMock(is_success=True)

    saga = OnboardingSaga(mock_db, mock_http_client)

    with pytest.raises(EMSError) as exc_info:
        await saga.execute(sample_payload)

    assert exc_info.value.code == "ONBOARDING_FAILED"
    assert mock_http_client.post.call_count == 2
    # Payroll compensation NOT called, Auth compensation called ONCE
    assert mock_http_client.delete.call_count == 1
    assert "users/" in mock_http_client.delete.call_args[0][0]


@pytest.mark.asyncio
async def test_saga_payroll_exception_triggers_auth_compensation(mock_db, mock_http_client, sample_payload):
    auth_resp = MagicMock(is_success=True)
    mock_http_client.post.side_effect = [auth_resp, Exception("Payroll timeout")]
    mock_http_client.delete.return_value = MagicMock(is_success=True)

    saga = OnboardingSaga(mock_db, mock_http_client)

    with pytest.raises(EMSError) as exc_info:
        await saga.execute(sample_payload)

    assert exc_info.value.code == "ONBOARDING_FAILED"
    assert mock_http_client.delete.call_count == 1
    assert "users/" in mock_http_client.delete.call_args[0][0]


@pytest.mark.asyncio
async def test_saga_step4_commit_exception_triggers_both_compensations(mock_db, mock_http_client, sample_payload):
    auth_resp = MagicMock(is_success=True)
    payroll_resp = MagicMock(is_success=True)
    mock_http_client.post.side_effect = [auth_resp, payroll_resp]
    mock_http_client.delete.return_value = MagicMock(is_success=True)

    # 1st commit (PENDING_ONBOARDING) succeeds, 2nd commit (ACTIVE + outbox) raises exception, 3rd commit (ONBOARDING_FAILED) succeeds
    mock_db.commit.side_effect = [None, Exception("DB write error during commit"), None]

    saga = OnboardingSaga(mock_db, mock_http_client)

    with pytest.raises(EMSError) as exc_info:
        await saga.execute(sample_payload)

    assert exc_info.value.code == "ONBOARDING_FAILED"
    # Both Payroll and Auth compensations called
    assert mock_http_client.delete.call_count == 2
    delete_urls = [call[0][0] for call in mock_http_client.delete.call_args_list]
    assert any("profiles/" in url for url in delete_urls)
    assert any("users/" in url for url in delete_urls)


@pytest.mark.asyncio
async def test_saga_compensations_exception_handling(mock_db, mock_http_client, sample_payload):
    auth_resp = MagicMock(is_success=True)
    payroll_resp = MagicMock(is_success=True)
    mock_http_client.post.side_effect = [auth_resp, payroll_resp]

    # Both delete calls raise exceptions during compensation
    mock_http_client.delete.side_effect = [Exception("Payroll comp delete error"), Exception("Auth comp delete error")]
    mock_db.commit.side_effect = [None, Exception("DB commit error"), None]


    saga = OnboardingSaga(mock_db, mock_http_client)

    with pytest.raises(EMSError) as exc_info:
        await saga.execute(sample_payload)

    assert exc_info.value.code == "ONBOARDING_FAILED"
    assert mock_http_client.delete.call_count == 2
