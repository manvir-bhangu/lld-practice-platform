import pytest

from app.domain.attempt import Attempt
from app.domain.content import TextDesign
from app.domain.enums import AttemptStatus
from app.domain.errors import InvalidStateTransition, InvalidSubmission
from app.domain.feedback import CriterionFeedback, Evaluation


def make_attempt():
    return Attempt(id="a1", problem_id="parking-lot", number=1)


def good_content():
    return TextDesign(sections={"classes": "ParkingLot, Spot, Ticket"})


def make_evaluation():
    fb = CriterionFeedback("classes", 4, 5, "has Spot", "no Vehicle", "add Vehicle", 0.8)
    return Evaluation("rule_based", (fb,))


def test_happy_path():
    a = make_attempt()
    a.save_draft(good_content())
    a.submit()
    assert a.status == AttemptStatus.SUBMITTED
    a.start_evaluation()
    a.complete([make_evaluation()])
    assert a.status == AttemptStatus.COMPLETED
    assert len(a.evaluations) == 1


def test_cannot_submit_empty():
    a = make_attempt()
    a.save_draft(TextDesign(sections={"classes": "   "}))
    with pytest.raises(InvalidSubmission):
        a.submit()


def test_cannot_submit_without_content():
    with pytest.raises(InvalidSubmission):
        make_attempt().submit()


def test_cannot_skip_evaluating():
    a = make_attempt()
    a.save_draft(good_content())
    a.submit()
    with pytest.raises(InvalidStateTransition):
        a.complete([make_evaluation()])


def test_cannot_edit_after_submit():
    a = make_attempt()
    a.save_draft(good_content())
    a.submit()
    with pytest.raises(InvalidStateTransition):
        a.save_draft(good_content())


def test_failed_evaluation_can_retry():
    a = make_attempt()
    a.save_draft(good_content())
    a.submit()
    a.start_evaluation()
    a.fail("LLM timeout")
    assert a.status == AttemptStatus.FAILED
    assert a.failure_reason == "LLM timeout"
    a.start_evaluation()
    assert a.status == AttemptStatus.EVALUATING
    assert a.failure_reason is None


def test_completed_attempt_cannot_be_evaluated_again():
    a = make_attempt()
    a.save_draft(good_content())
    a.submit()
    a.start_evaluation()
    a.complete([make_evaluation()])
    with pytest.raises(InvalidStateTransition):
        a.start_evaluation()


def test_score_out_of_range_rejected():
    with pytest.raises(ValueError):
        CriterionFeedback("x", 9, 5, "e", "c", "s", 0.5)