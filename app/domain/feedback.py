from dataclasses import dataclass


@dataclass(frozen=True)
class CriterionFeedback:
    criterion_key: str
    score: int
    max_score: int
    evidence: str
    concern: str
    suggestion: str
    confidence: float  # 0.0 - 1.0

    def __post_init__(self):
        if not 0 <= self.score <= self.max_score:
            raise ValueError(f"score {self.score} outside 0..{self.max_score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class Evaluation:
    evaluator_name: str
    feedback: tuple[CriterionFeedback, ...]
    summary: str = ""

    @property
    def total_score(self) -> int:
        return sum(f.score for f in self.feedback)

    @property
    def max_score(self) -> int:
        return sum(f.max_score for f in self.feedback)