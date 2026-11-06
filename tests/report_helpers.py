from datetime import UTC, datetime


def report_payload(**changes):
    return {"type": "found", "category": "phone", "title": "Black phone",
            "description": "Black phone with a distinctive case", "location_text": "Central station",
            "event_date": datetime.now(UTC).date().isoformat(), **changes}
