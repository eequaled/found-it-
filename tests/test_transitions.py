from itertools import product

import pytest

from app.db.generated.enums import ClaimStatus as C, ReportStatus as R
from app.errors import DomainError
from app.services.transitions import (
    CLAIM_TRANSITIONS, REPORT_TRANSITIONS,
    require_valid_claim_transition, require_valid_report_transition,
)

# Independent acceptance-criteria oracle, not generated from the implementation.
REPORT_EDGES = {(R.PENDING_REVIEW, R.OPEN): False, (R.PENDING_REVIEW, R.REJECTED): True,
                (R.PENDING_REVIEW, R.REMOVED): True, (R.OPEN, R.RESOLVED): True, (R.OPEN, R.REMOVED): True}
CLAIM_EDGES = {(C.PENDING, C.APPROVED): False, (C.PENDING, C.REJECTED): True, (C.PENDING, C.WITHDRAWN): False}
POLICIES = [(require_valid_report_transition, current, target, required) for (current, target), required in REPORT_EDGES.items()]
POLICIES += [(require_valid_claim_transition, current, target, required) for (current, target), required in CLAIM_EDGES.items()]


def assert_conflict(error, current, target):
    assert error.code == "invalid_transition" and error.status_code == 409
    assert str(current) in error.message and str(target) in error.message


@pytest.mark.parametrize("current,target", list(product(R, repeat=2)))
def test_every_report_pair_including_self_and_terminal_transitions(current, target):
    if (current, target) in REPORT_EDGES:
        assert require_valid_report_transition(current, target, "  reviewed  ") == "reviewed"
    else:
        with pytest.raises(DomainError) as error:
            require_valid_report_transition(current, target, "reviewed")
        assert_conflict(error.value, current, target)


@pytest.mark.parametrize("current,target", list(product(C, repeat=2)))
def test_every_claim_pair_including_self_and_terminal_transitions(current, target):
    if (current, target) in CLAIM_EDGES:
        assert require_valid_claim_transition(current, target, "  reviewed  ") == "reviewed"
    else:
        with pytest.raises(DomainError) as error:
            require_valid_claim_transition(current, target, "reviewed")
        assert_conflict(error.value, current, target)


@pytest.mark.parametrize("guard,current,target,required", POLICIES)
def test_missing_note_policy_matches_each_edge(guard, current, target, required):
    if required:
        with pytest.raises(DomainError) as error:
            guard(current, target)
        assert error.value.code == "invalid_note" and error.value.status_code == 422
    else:
        assert guard(current, target) is None


@pytest.mark.parametrize("note", ["", " \t\n", "x" * 1001, 123, False, ["private note"]])
@pytest.mark.parametrize("guard,current,target,required", POLICIES)
def test_invalid_supplied_notes_fail_even_when_notes_are_optional(guard, current, target, required, note):
    with pytest.raises(DomainError) as error:
        guard(current, target, note)
    assert error.value.code == "invalid_note" and error.value.status_code == 422
    assert "private note" not in error.value.message


@pytest.mark.parametrize("guard,current,target,required", POLICIES)
def test_note_boundary_and_whitespace_normalization(guard, current, target, required):
    assert guard(current, target, "  " + "é" * 1000 + "\n") == "é" * 1000
    assert guard(current, target, " a ") == "a"


@pytest.mark.parametrize("guard,current,target", [
    (require_valid_report_transition, R.PENDING_REVIEW, C.REJECTED),
    (require_valid_claim_transition, C.PENDING, R.REJECTED),
    (require_valid_report_transition, "pending_review", R.OPEN),
    (require_valid_report_transition, R.PENDING_REVIEW, "open"),
    (require_valid_claim_transition, "pending", C.APPROVED),
    (require_valid_claim_transition, C.PENDING, "approved"),
    (require_valid_report_transition, None, R.OPEN),
    (require_valid_claim_transition, C.PENDING, None),
])
def test_unvalidated_or_cross_domain_values_cannot_exploit_strenum_equality(guard, current, target):
    with pytest.raises(DomainError) as error:
        guard(current, target, "reviewed")
    assert_conflict(error.value, current, target)


@pytest.mark.parametrize("table,enum,expected", [(REPORT_TRANSITIONS, R, REPORT_EDGES), (CLAIM_TRANSITIONS, C, CLAIM_EDGES)])
def test_tables_are_complete_immutable_and_expose_note_policy_without_another_rule_list(table, enum, expected):
    assert set(table) == set(enum)
    assert {(current, target): required for current, targets in table.items() for target, required in targets.items()} == expected
    for current in enum:
        with pytest.raises(TypeError):
            table[current] = {}
        with pytest.raises(TypeError):
            table[current][current] = False


def test_invalid_edge_takes_precedence_over_note_validation():
    with pytest.raises(DomainError) as error:
        require_valid_report_transition(R.RESOLVED, R.OPEN, "")
    assert_conflict(error.value, R.RESOLVED, R.OPEN)
