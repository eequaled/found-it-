"""The sole status-edge and note policy; no authorization, SQL or side effects.

The immutable nested maps associate each allowed target with note_required.
Write services must still authenticate, lock report before claim, re-read state,
and persist changes/history atomically. These guards do not perform those steps.
"""
from types import MappingProxyType

from app.db.generated.enums import ClaimStatus, ReportStatus
from app.errors import DomainError

REPORT_TRANSITIONS = MappingProxyType({
    ReportStatus.PENDING_REVIEW: MappingProxyType({
        ReportStatus.OPEN: False, ReportStatus.REJECTED: True, ReportStatus.REMOVED: True,
    }),
    ReportStatus.OPEN: MappingProxyType({ReportStatus.RESOLVED: True, ReportStatus.REMOVED: True}),
    ReportStatus.RESOLVED: MappingProxyType({}),
    ReportStatus.REJECTED: MappingProxyType({}),
    ReportStatus.REMOVED: MappingProxyType({}),
})
CLAIM_TRANSITIONS = MappingProxyType({
    ClaimStatus.PENDING: MappingProxyType({
        ClaimStatus.APPROVED: False, ClaimStatus.REJECTED: True, ClaimStatus.WITHDRAWN: False,
    }),
    ClaimStatus.APPROVED: MappingProxyType({}),
    ClaimStatus.REJECTED: MappingProxyType({}),
    ClaimStatus.WITHDRAWN: MappingProxyType({}),
})


def _note(note, required):
    if note is None:
        if required:
            raise DomainError("invalid_note", "A note is required for this transition", 422)
        return None
    if not isinstance(note, str) or not 1 <= len(note.strip()) <= 1000:
        raise DomainError("invalid_note", "Note must contain 1 to 1000 characters after trimming", 422)
    return note.strip()


def require_valid_report_transition(current: ReportStatus, target: ReportStatus, note: str | None = None) -> str | None:
    # StrEnum values from different domains can compare equal; reject wrong
    # enum classes and unvalidated strings rather than silently crossing domains.
    if type(current) is not ReportStatus or type(target) is not ReportStatus or target not in REPORT_TRANSITIONS[current]:
        raise DomainError("invalid_transition", f"Cannot change report status from {current} to {target}", 409)
    return _note(note, REPORT_TRANSITIONS[current][target])


def require_valid_claim_transition(current: ClaimStatus, target: ClaimStatus, note: str | None = None) -> str | None:
    if type(current) is not ClaimStatus or type(target) is not ClaimStatus or target not in CLAIM_TRANSITIONS[current]:
        raise DomainError("invalid_transition", f"Cannot change claim status from {current} to {target}", 409)
    return _note(note, CLAIM_TRANSITIONS[current][target])
