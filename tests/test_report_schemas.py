from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.api.schemas import ReportCreate


from tests.report_helpers import report_payload


@pytest.mark.parametrize("field,value", [
    ("title", "  "), ("title", "x" * 121), ("description", "short"),
    ("description", "x" * 5001), ("location_text", "x"), ("location_text", "x" * 201),
    ("type", "invented"), ("category", "invented"), ("contact_email", "not-an-email"),
    ("contact_phone", "abc"), ("contact_phone", "1--"), ("contact_name", " "),
    ("event_date", "not-a-date"), ("event_date", 0), ("event_date", "2020-01-01T00:00:00"),
    ("event_date", (datetime.now(UTC).date() + timedelta(days=30)).isoformat()),
    ("status", "open"), ("tracking_token_hash", "attacker-controlled"), ("photo_path", "private.jpg"),
])
def test_report_validation_names_the_invalid_field(field, value):
    body = report_payload()
    body[field] = value
    with pytest.raises(ValidationError) as error:
        ReportCreate.model_validate(body)
    assert error.value.errors()[0]["loc"] == (field,)


def test_optional_contacts_and_whitespace_normalization():
    body = report_payload()
    body["title"] = "  هاتف téléphone  "
    body["contact_email"] = "owner@example.com"
    body["contact_phone"] = "+213 555 123 456"
    result = ReportCreate.model_validate(body)
    assert result.title == "هاتف téléphone"
    assert result.contact_email == "owner@example.com"
    assert ReportCreate.model_validate(report_payload()).contact_phone is None
