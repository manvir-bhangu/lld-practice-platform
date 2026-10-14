from app.domain.content import TEXT_DESIGN_SECTIONS, SubmissionContent, TextDesign
from app.domain.feedback import CriterionFeedback, Evaluation
from app.domain.problem import Problem
from app.evaluators.base import EvaluationError, Evaluator
import re
def _norm(text: str) -> str:
    return re.sub(r"[\s_\-]+", "", text.lower())
class RuleBasedEvaluator(Evaluator):
    name = "rule_based"
    supported_formats = (TextDesign.format,)
    criteria_keys = ("completeness", "entity_coverage")

    def evaluate(self, problem: Problem, content: SubmissionContent) -> Evaluation:
        if not isinstance(content, TextDesign) or not self.supports(content):
            raise EvaluationError(f"{self.name} cannot evaluate format '{content.format}'")
        feedback = (
            self._completeness(problem, content),
            self._entity_coverage(problem, content),
        )
        total = sum(f.score for f in feedback)
        maximum = sum(f.max_score for f in feedback)
        return Evaluation(self.name, feedback, summary=f"Automated structure check: {total}/{maximum}")

    def _completeness(self, problem: Problem, content: TextDesign) -> CriterionFeedback:
        max_score = problem.rubric.get("completeness").max_score
        filled = [s for s in TEXT_DESIGN_SECTIONS if content.sections.get(s, "").strip()]
        missing = [s for s in TEXT_DESIGN_SECTIONS if s not in filled]
        score = round(max_score * len(filled) / len(TEXT_DESIGN_SECTIONS))
        return CriterionFeedback(
            criterion_key="completeness",
            score=score,
            max_score=max_score,
            evidence=f"Sections filled: {', '.join(filled) or 'none'}",
            concern=f"Missing sections: {', '.join(missing)}" if missing else "",
            suggestion="Fill in the missing sections, even briefly." if missing else "",
            confidence=1.0,  # a section is either there or it isn't
        )

    def _entity_coverage(self, problem: Problem, content: TextDesign) -> CriterionFeedback:
        max_score = problem.rubric.get("entity_coverage").max_score
        expected = problem.expected_entities
        text = _norm(content.as_text())
        found = [e for e in expected if _norm(e) in text]
        missing = [e for e in expected if e not in found]
        score = round(max_score * len(found) / len(expected)) if expected else max_score
        return CriterionFeedback(
            criterion_key="entity_coverage",
            score=score,
            max_score=max_score,
            evidence=f"Mentioned: {', '.join(found) or 'none'}",
            concern=f"Not mentioned: {', '.join(missing)}" if missing else "",
            suggestion=("Check whether these concepts are modelled, "
                        "perhaps under a different name.") if missing else "",
            confidence=0.6,  # keyword match: a valid design may use other names
        )