import json
import logging
from io import StringIO
from ems_common.correlation import set_correlation_id
from ems_common.logging import JSONCorrelationFormatter


def test_logging_includes_correlation_id():
    formatter = JSONCorrelationFormatter()
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    logger.handlers = [handler]

    set_correlation_id("test-corr-1234")
    logger.info("Test log message")

    output = stream.getvalue()
    log_record = json.loads(output)

    assert log_record["message"] == "Test log message"
    assert log_record["correlation_id"] == "test-corr-1234"
    assert "timestamp" in log_record
    assert log_record["level"] == "INFO"
