import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from ems_common.consumer import ConsumerBase, is_event_processed, process_idempotent_event
from ems_common.outbox import OutboxBase, OutboxMessage, add_outbox_event


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    OutboxBase.metadata.create_all(engine)
    ConsumerBase.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_outbox_row_creation(db_session: Session):
    event_type = "EmployeeOnboarded"
    payload = {"employee_id": "emp-101", "name": "John Doe"}
    corr_id = "corr-abc-123"

    msg = add_outbox_event(db_session, event_type=event_type, payload=payload, correlation_id=corr_id)
    db_session.commit()

    saved_msg = db_session.query(OutboxMessage).filter_by(id=msg.id).first()
    assert saved_msg is not None
    assert saved_msg.event_type == "EmployeeOnboarded"
    assert json.loads(saved_msg.payload) == payload
    assert saved_msg.correlation_id == corr_id
    assert saved_msg.published_at is None


def test_consumer_idempotency_blocks_duplicate(db_session: Session):
    event_id = "evt-uuid-5555"
    execution_counter = {"count": 0}

    def sample_handler():
        execution_counter["count"] += 1

    # First execution should run handler and record event
    result1 = process_idempotent_event(db_session, event_id, sample_handler)
    assert result1 is True
    assert execution_counter["count"] == 1
    assert is_event_processed(db_session, event_id) is True

    # Second execution with same event_id should be skipped
    result2 = process_idempotent_event(db_session, event_id, sample_handler)
    assert result2 is False
    assert execution_counter["count"] == 1
