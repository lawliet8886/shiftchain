import json
import logging

from shiftchain.observability import JsonFormatter


def test_structured_log_is_valid_json() -> None:
    record = logging.LogRecord("shiftchain", logging.INFO, __file__, 1, "event_name", (), None)
    record.structured_fields = {"request_id": "REQ-001", "state": "VERIFIED"}
    payload = json.loads(JsonFormatter().format(record))
    assert payload["event"] == "event_name"
    assert payload["request_id"] == "REQ-001"

