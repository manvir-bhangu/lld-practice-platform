import json
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.content import TextDesign
from app.domain.enums import AttemptStatus
from app.domain.errors import InvalidStateTransition, InvalidSubmission, NotFound
from app.evaluators.base import Evaluator
from app.evaluators.llm import LLMEvaluator
from app.evaluators.rule_based import RuleBasedEvaluator
from app.repository.in_memory import InMemoryAttemptRepository
from app.repository.problems import build_default_catalog
from app.services.practice_service import PracticeService

S = AttemptStatus

FULL_DESIGN = TextDesign(sections={
    "assumptions": "Single building",
    "classes": "ParkingLot, Spot, Ticket, Vehicle",
    "relationships": "ParkingLot has many Spots",
    "key_flows": "Park: find spot, issue ticket",
    "extensibility": "Pricing is a strategy",
})


def llm_ok() -> str:
    keys = ["responsibilities", "coupling_cohesion", "extensibility", "edge_cases_tradeoffs"]
    return json.dumps({"summary": "ok", "criteria": [
        {"criterion": k, "score": 4, "evidence": "e", "concern": "c",
         "suggestion": "s", "confidence": 0.7} for k in keys]})


class ScriptedLLM:
    """Returns (or raises) one scripted item per call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class ExplodingEvaluator(Evaluator):
    name = "exploding"
    supported_formats = (TextDesign.format,)
    criteria_keys = ()

    def evaluate(self, problem, content):
        raise ZeroDivisionError("boom")


class RacingRepository(InMemoryAttemptRepository):
    """Simulates another worker claiming the attempt between our read and our save."""

    def __init__(self):
        super().__init__()
        self.race_once = False

    def get(self, attempt_id):
        attempt = super().get(attempt_id)
        if self.race_once:
            self.race_once = False
            rival = super().get(attempt_id)
            rival.start_evaluation()
            self.save(rival)
        return attempt


def build_service(llm, repo=None):
    repo = repo or InMemoryAttemptRepository()
    service = PracticeService(
        catalog=build_default_catalog(),
        repository=repo,
        evaluators=[RuleBasedEvaluator(), LLMEvaluator(llm)],
    )
    return service, repo


def submitted_attempt(service, problem_id="parking-lot"):
    attempt = service.start_attempt(problem_id)
    service.save_draft(attempt.id, FULL_DESIGN)
    return service.submit(attempt.id)


# ---------- starting, drafting, submitting ----------

def test_attempts_are_numbered_per_problem():
    service, _ = build_service(ScriptedLLM())
    first = submitted_attempt(service)
    second = service.start_attempt("parking-lot")
    other = service.start_attempt("elevator")
    assert (first.number, second.number, other.number) == (1, 2, 1)


def test_start_attempt_reuses_open_draft():
    service, _ = build_service(ScriptedLLM())
    assert service.start_attempt("parking-lot").id == service.start_attempt("parking-lot").id


def test_start_attempt_unknown_problem():
    service, _ = build_service(ScriptedLLM())
    with pytest.raises(NotFound):
        service.start_attempt("nope")


def test_cannot_edit_after_submit():
    service, _ = build_service(ScriptedLLM())
    attempt = submitted_attempt(service)
    with pytest.raises(InvalidStateTransition):
        service.save_draft(attempt.id, FULL_DESIGN)


def test_submit_empty_rejected():
    service, _ = build_service(ScriptedLLM())
    attempt = service.start_attempt("parking-lot")
    with pytest.raises(InvalidSubmission):
        service.submit(attempt.id)


def test_submit_is_idempotent():
    service, _ = build_service(ScriptedLLM())
    attempt = submitted_attempt(service)
    again = service.submit(attempt.id)
    assert again.status == S.SUBMITTED
    assert again.version == attempt.version


# ---------- evaluation ----------

def test_evaluate_completes_with_both_evaluators():
    llm = ScriptedLLM(llm_ok())
    service, _ = build_service(llm)
    attempt = submitted_attempt(service)
    done = service.evaluate(attempt.id)
    assert done.status == S.COMPLETED
    assert [e.evaluator_name for e in done.evaluations] == ["rule_based", "llm"]
    assert llm.calls == 1
    assert service.get_attempt(attempt.id).status == S.COMPLETED


def test_evaluate_twice_calls_llm_once():
    llm = ScriptedLLM(llm_ok())
    service, _ = build_service(llm)
    attempt = submitted_attempt(service)
    service.evaluate(attempt.id)
    service.evaluate(attempt.id)
    assert llm.calls == 1


def test_cannot_evaluate_a_draft():
    service, _ = build_service(ScriptedLLM())
    attempt = service.start_attempt("parking-lot")
    with pytest.raises(InvalidStateTransition):
        service.evaluate(attempt.id)


def test_llm_failure_marks_failed_then_retry_succeeds():
    llm = ScriptedLLM(TimeoutError("timed out"), llm_ok())
    service, _ = build_service(llm)
    attempt = submitted_attempt(service)

    failed = service.evaluate(attempt.id)
    assert failed.status == S.FAILED
    assert "LLM call failed" in failed.failure_reason
    assert failed.evaluations == []

    done = service.evaluate(attempt.id)
    assert done.status == S.COMPLETED
    assert done.failure_reason is None
    assert llm.calls == 2


def test_garbage_llm_output_marks_failed():
    service, _ = build_service(ScriptedLLM("this is not json"))
    attempt = submitted_attempt(service)
    result = service.evaluate(attempt.id)
    assert result.status == S.FAILED
    assert "invalid JSON" in result.failure_reason


def test_unexpected_crash_never_leaves_attempt_evaluating():
    service = PracticeService(build_default_catalog(), InMemoryAttemptRepository(),
                              [ExplodingEvaluator()])
    attempt = submitted_attempt(service)
    result = service.evaluate(attempt.id)
    assert result.status == S.FAILED
    assert "ZeroDivisionError" in result.failure_reason


def test_no_evaluator_for_format_fails_cleanly():
    service = PracticeService(build_default_catalog(), InMemoryAttemptRepository(), [])
    attempt = submitted_attempt(service)
    result = service.evaluate(attempt.id)
    assert result.status == S.FAILED
    assert "No evaluator supports" in result.failure_reason


# ---------- duplicate processing ----------

def test_evaluate_while_already_evaluating_does_nothing():
    llm = ScriptedLLM()
    service, repo = build_service(llm)
    attempt = submitted_attempt(service)
    claimed = repo.get(attempt.id)
    claimed.start_evaluation()
    repo.save(claimed)

    result = service.evaluate(attempt.id)
    assert result.status == S.EVALUATING
    assert llm.calls == 0


def test_losing_the_claim_race_does_nothing():
    llm = ScriptedLLM()
    repo = RacingRepository()
    service, _ = build_service(llm, repo)
    attempt = submitted_attempt(service)

    repo.race_once = True  # a rival claims it right after our read
    result = service.evaluate(attempt.id)
    assert result.status == S.EVALUATING
    assert llm.calls == 0


# ---------- stuck evaluations ----------

def test_stuck_evaluation_is_recovered_and_can_be_retried():
    llm = ScriptedLLM(llm_ok())
    service, repo = build_service(llm)
    attempt = submitted_attempt(service)
    claimed = repo.get(attempt.id)  # a worker claims it, then "crashes"
    claimed.start_evaluation()
    repo.save(claimed)

    now = datetime.now(timezone.utc)
    timeout = timedelta(minutes=5)
    assert service.recover_stuck_evaluations(timeout, now=now + timedelta(minutes=1)) == []

    recovered = service.recover_stuck_evaluations(timeout, now=now + timedelta(minutes=10))
    assert [a.status for a in recovered] == [S.FAILED]
    assert "timed out" in recovered[0].failure_reason

    assert service.evaluate(attempt.id).status == S.COMPLETED


# ---------- history ----------

def test_history_newest_first_and_validates_problem():
    service, _ = build_service(ScriptedLLM())
    submitted_attempt(service)
    submitted_attempt(service)
    submitted_attempt(service, "elevator")
    assert [a.number for a in service.history("parking-lot")] == [2, 1]
    assert len(service.history()) == 3
    with pytest.raises(NotFound):
        service.history("nope")