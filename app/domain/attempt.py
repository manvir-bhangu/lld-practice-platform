from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.content import SubmissionContent
from app.domain.enums import AttemptStatus
from app.domain.errors import InvalidStateTransition, InvalidSubmission
from app.domain.feedback import Evaluation

S = AttemptStatus

_ALLOWED = {
    S.DRAFT: {S.SUBMITTED},
    S.SUBMITTED: {S.EVALUATING},
    S.EVALUATING: {S.COMPLETED, S.FAILED},
    S.FAILED: {S.EVALUATING},  # retry evaluation
    S.COMPLETED: set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Attempt:
    id: str
    problem_id: str
    number: int  # 1st, 2nd, 3rd attempt on this problem
    status: AttemptStatus = S.DRAFT
    content: SubmissionContent | None = None
    evaluations: list[Evaluation] = field(default_factory=list)
    failure_reason: str | None = None
    created_at: datetime = field(default_factory=_now)
    submitted_at: datetime | None = None

    def _move_to(self, new_status: AttemptStatus) -> None:
        if new_status not in _ALLOWED[self.status]:
            raise InvalidStateTransition(
                f"Cannot go from {self.status.value} to {new_status.value}"
            )
        self.status = new_status

    def save_draft(self, content: SubmissionContent) -> None:
        if self.status != S.DRAFT:
            raise InvalidStateTransition("Only a draft can be edited")
        self.content = content

    def submit(self) -> None:
        if self.content is None or self.content.is_blank():
            raise InvalidSubmission("Cannot submit an empty design")
        self._move_to(S.SUBMITTED)
        self.submitted_at = _now()

    def start_evaluation(self) -> None:
        self._move_to(S.EVALUATING)
        self.failure_reason = None

    def complete(self, evaluations: list[Evaluation]) -> None:
        if not evaluations:
            raise InvalidSubmission("Completed attempt needs at least one evaluation")
        self._move_to(S.COMPLETED)
        self.evaluations = list(evaluations)

    def fail(self, reason: str) -> None:
        self._move_to(S.FAILED)
        self.failure_reason = reason