import pytest

from app.domain.default_rubric import DEFAULT_RUBRIC
from app.domain.errors import NotFound
from app.evaluators.llm import LLMEvaluator
from app.evaluators.rule_based import RuleBasedEvaluator
from app.repository.problems import build_default_catalog


def test_catalog_has_three_problems():
    ids = [p.id for p in build_default_catalog().list()]
    assert ids == ["parking-lot", "elevator", "vending-machine"]


def test_every_problem_is_well_formed():
    for p in build_default_catalog().list():
        assert p.requirements
        assert p.expected_entities
        assert p.rubric.criteria


def test_unknown_problem_raises():
    with pytest.raises(NotFound):
        build_default_catalog().get("nope")


def test_every_rubric_criterion_is_judged_by_exactly_one_evaluator():
    judged = list(RuleBasedEvaluator.criteria_keys) + list(LLMEvaluator.criteria_keys)
    rubric_keys = [c.key for c in DEFAULT_RUBRIC.criteria]
    assert sorted(judged) == sorted(rubric_keys)