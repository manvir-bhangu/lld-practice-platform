from abc import ABC, abstractmethod
from typing import ClassVar

from app.domain.content import SubmissionContent
from app.domain.feedback import Evaluation
from app.domain.problem import Problem


class EvaluationError(Exception):
    """Evaluator could not produce a valid result (timeout, bad output, etc.)."""


class Evaluator(ABC):
    name: ClassVar[str]
    supported_formats: ClassVar[tuple[str, ...]]
    criteria_keys: ClassVar[tuple[str, ...]]  # which rubric criteria this one judges

    def supports(self, content: SubmissionContent) -> bool:
        return content.format in self.supported_formats

    @abstractmethod
    def evaluate(self, problem: Problem, content: SubmissionContent) -> Evaluation: ...