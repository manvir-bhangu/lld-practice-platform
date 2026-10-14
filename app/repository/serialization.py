import json

from app.domain.feedback import CriterionFeedback, Evaluation


def evaluations_to_json(evaluations: list[Evaluation]) -> str:
    return json.dumps([
        {
            "evaluator_name": e.evaluator_name,
            "summary": e.summary,
            "feedback": [
                {
                    "criterion_key": f.criterion_key,
                    "score": f.score,
                    "max_score": f.max_score,
                    "evidence": f.evidence,
                    "concern": f.concern,
                    "suggestion": f.suggestion,
                    "confidence": f.confidence,
                }
                for f in e.feedback
            ],
        }
        for e in evaluations
    ])


def evaluations_from_json(raw: str) -> list[Evaluation]:
    return [
        Evaluation(
            evaluator_name=e["evaluator_name"],
            summary=e.get("summary", ""),
            feedback=tuple(CriterionFeedback(**f) for f in e["feedback"]),
        )
        for e in json.loads(raw)
    ]