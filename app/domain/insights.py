from dataclasses import dataclass
from enum import Enum

from app.domain.attempt import Attempt
from app.domain.enums import AttemptStatus
from app.domain.feedback import CriterionFeedback
from app.domain.problem import Problem

WEAK_FRACTION = 0.6     # below this share of max score = weak
RECURRENCE_WINDOW = 2   # weak in this many latest attempts in a row = recurring


class TrendStatus(str, Enum):
    NOT_ENOUGH_DATA = "NOT_ENOUGH_DATA"
    IMPROVING = "IMPROVING"
    DECLINING = "DECLINING"
    STEADY = "STEADY"
    RECURRING_WEAKNESS = "RECURRING_WEAKNESS"


@dataclass(frozen=True)
class CriterionTrend:
    criterion_key: str
    name: str
    max_score: int
    scores: tuple[int, ...]  # oldest first, one per completed attempt
    status: TrendStatus
    latest_concern: str = ""
    latest_suggestion: str = ""

    @property
    def change(self) -> int | None:
        """Points gained or lost versus the previous attempt."""
        if len(self.scores) < 2:
            return None
        return self.scores[-1] - self.scores[-2]


@dataclass(frozen=True)
class ProgressInsights:
    problem_id: str
    attempts_analyzed: int
    overall_percent: tuple[int, ...]  # oldest first
    trends: tuple[CriterionTrend, ...]

    @property
    def recurring_weaknesses(self) -> tuple[CriterionTrend, ...]:
        return tuple(t for t in self.trends if t.status == TrendStatus.RECURRING_WEAKNESS)


def _feedback_by_criterion(attempt: Attempt) -> dict[str, CriterionFeedback]:
    # Each criterion is judged by exactly one evaluator (enforced by a catalog
    # test), so keeping the first occurrence is safe.
    found: dict[str, CriterionFeedback] = {}
    for evaluation in attempt.evaluations:
        for fb in evaluation.feedback:
            found.setdefault(fb.criterion_key, fb)
    return found


def _is_weak(score: int, max_score: int) -> bool:
    return max_score > 0 and score / max_score < WEAK_FRACTION


def _classify(scores: tuple[int, ...], max_score: int) -> TrendStatus:
    if len(scores) < 2:
        return TrendStatus.NOT_ENOUGH_DATA
    if all(_is_weak(s, max_score) for s in scores[-RECURRENCE_WINDOW:]):
        return TrendStatus.RECURRING_WEAKNESS
    if scores[-1] > scores[-2]:
        return TrendStatus.IMPROVING
    if scores[-1] < scores[-2]:
        return TrendStatus.DECLINING
    return TrendStatus.STEADY


def analyze_progress(problem: Problem, attempts: list[Attempt]) -> ProgressInsights:
    completed = sorted(
        (a for a in attempts
         if a.problem_id == problem.id and a.status == AttemptStatus.COMPLETED),
        key=lambda a: a.number,
    )
    per_attempt = [_feedback_by_criterion(a) for a in completed]

    overall = []
    for fbs in per_attempt:
        total = sum(f.score for f in fbs.values())
        maximum = sum(f.max_score for f in fbs.values())
        overall.append(round(100 * total / maximum) if maximum else 0)

    trends = []
    for criterion in problem.rubric.criteria:
        feedbacks = [fbs[criterion.key] for fbs in per_attempt if criterion.key in fbs]
        scores = tuple(f.score for f in feedbacks)
        latest = feedbacks[-1] if feedbacks else None
        trends.append(CriterionTrend(
            criterion_key=criterion.key,
            name=criterion.name,
            max_score=criterion.max_score,
            scores=scores,
            status=_classify(scores, criterion.max_score),
            latest_concern=latest.concern if latest else "",
            latest_suggestion=latest.suggestion if latest else "",
        ))

    return ProgressInsights(
        problem_id=problem.id,
        attempts_analyzed=len(completed),
        overall_percent=tuple(overall),
        trends=tuple(trends),
    )