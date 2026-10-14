from dataclasses import dataclass


@dataclass(frozen=True)
class Criterion:
    key: str
    name: str
    description: str
    max_score: int = 5


@dataclass(frozen=True)
class Rubric:
    criteria: tuple[Criterion, ...]

    def get(self, key: str) -> Criterion:
        for c in self.criteria:
            if c.key == key:
                return c
        raise KeyError(f"Unknown criterion: {key}")

    @property
    def max_total(self) -> int:
        return sum(c.max_score for c in self.criteria)


@dataclass(frozen=True)
class Problem:
    id: str
    title: str
    summary: str
    requirements: tuple[str, ...]
    expected_entities: tuple[str, ...]  # used by the deterministic evaluator
    rubric: Rubric