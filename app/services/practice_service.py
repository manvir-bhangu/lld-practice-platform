import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from app.domain.attempt import Attempt
from app.domain.content import SubmissionContent
from app.domain.enums import AttemptStatus
from app.domain.errors import ConcurrentModification
from app.domain.feedback import Evaluation
from app.domain.problem import Problem
from app.evaluators.base import EvaluationError, Evaluator
from app.repository.base import AttemptRepository
from app.repository.problems import ProblemCatalog

log = logging.getLogger(__name__)
S = AttemptStatus


class PracticeService:
    def __init__(
        self,
        catalog: ProblemCatalog,
        repository: AttemptRepository,
        evaluators: list[Evaluator],
        id_factory: Callable[[], str] | None = None,
    ):
        self._catalog = catalog
        self._repo = repository
        self._evaluators = list(evaluators)
        self._new_id = id_factory or (lambda: uuid.uuid4().hex)

    # ---------- problems ----------

    def list_problems(self) -> list[Problem]:
        return self._catalog.list()

    def get_problem(self, problem_id: str) -> Problem:
        return self._catalog.get(problem_id)

    # ---------- attempts ----------

    def start_attempt(self, problem_id: str) -> Attempt:
        """Returns the open draft if there is one, so a double click doesn't
        create two attempts."""
        self._catalog.get(problem_id)  # NotFound for unknown problems
        for _ in range(3):
            existing = self._repo.list_for_problem(problem_id)
            open_draft = next((a for a in existing if a.status == S.DRAFT), None)
            if open_draft is not None:
                return open_draft
            number = max((a.number for a in existing), default=0) + 1
            attempt = Attempt(id=self._new_id(), problem_id=problem_id, number=number)
            try:
                self._repo.add(attempt)
                return attempt
            except ConcurrentModification:
                continue  # someone took this number; recompute and retry
        raise ConcurrentModification("Could not start an attempt, please retry")

    def save_draft(self, attempt_id: str, content: SubmissionContent) -> Attempt:
        attempt = self._repo.get(attempt_id)
        attempt.save_draft(content)
        self._repo.save(attempt)
        return attempt

    def submit(self, attempt_id: str) -> Attempt:
        """Idempotent: submitting an already-submitted attempt returns it unchanged."""
        attempt = self._repo.get(attempt_id)
        if attempt.status != S.DRAFT:
            return attempt
        attempt.submit()
        try:
            self._repo.save(attempt)
        except ConcurrentModification:
            current = self._repo.get(attempt_id)
            if current.status == S.DRAFT:
                raise  # the conflict was something else, not a duplicate submit
            return current
        return attempt

    def get_attempt(self, attempt_id: str) -> Attempt:
        return self._repo.get(attempt_id)

    def history(self, problem_id: str | None = None) -> list[Attempt]:
        """Newest first."""
        if problem_id is None:
            return self._repo.list_all()
        self._catalog.get(problem_id)
        return sorted(self._repo.list_for_problem(problem_id),
                      key=lambda a: a.number, reverse=True)

    # ---------- evaluation ----------

    def evaluate(self, attempt_id: str) -> Attempt:
        """Run evaluation. Safe to call repeatedly and from several workers:
        - COMPLETED / EVALUATING attempts are returned untouched
        - only one caller can claim a SUBMITTED or FAILED attempt (optimistic lock)
        - any failure ends in FAILED, never stuck in EVALUATING
        """
        attempt = self._repo.get(attempt_id)
        problem = self._catalog.get(attempt.problem_id)

        if attempt.status in (S.EVALUATING, S.COMPLETED):
            return attempt

        attempt.start_evaluation()  # raises InvalidStateTransition for a DRAFT
        try:
            self._repo.save(attempt)  # this save is the "claim"
        except ConcurrentModification:
            return self._repo.get(attempt_id)  # another worker won; nothing to do

        try:
            attempt.complete(self._run_evaluators(problem, attempt))
        except EvaluationError as exc:
            attempt.fail(str(exc))
        except Exception as exc:
            log.exception("Unexpected error evaluating attempt %s", attempt_id)
            attempt.fail(f"Unexpected error: {type(exc).__name__}")

        try:
            self._repo.save(attempt)
            return attempt
        except ConcurrentModification:
            # e.g. stuck-evaluation recovery already failed this attempt
            return self._repo.get(attempt_id)

    def _run_evaluators(self, problem: Problem, attempt: Attempt) -> list[Evaluation]:
        content = attempt.content
        applicable = [e for e in self._evaluators if e.supports(content)]
        if not applicable:
            raise EvaluationError(f"No evaluator supports format '{content.format}'")
        return [e.evaluate(problem, content) for e in applicable]

    def recover_stuck_evaluations(
        self, timeout: timedelta, now: datetime | None = None
    ) -> list[Attempt]:
        """If a worker died mid-evaluation the attempt would sit in EVALUATING
        forever. Mark those FAILED so the learner can retry."""
        now = now or datetime.now(timezone.utc)
        recovered = []
        for attempt in self._repo.list_all():
            started = attempt.evaluation_started_at
            if attempt.status != S.EVALUATING or started is None or now - started < timeout:
                continue
            attempt.fail("Evaluation timed out; please retry")
            try:
                self._repo.save(attempt)
            except ConcurrentModification:
                continue  # it finished just now
            recovered.append(attempt)
        return recovered