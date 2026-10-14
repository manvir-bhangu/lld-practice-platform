import copy

from app.domain.attempt import Attempt
from app.domain.errors import ConcurrentModification, NotFound
from app.repository.base import AttemptRepository


class InMemoryAttemptRepository(AttemptRepository):
    def __init__(self):
        self._items: dict[str, Attempt] = {}

    def add(self, attempt: Attempt) -> None:
        if attempt.id in self._items:
            raise ConcurrentModification(f"Attempt {attempt.id} already exists")
        if any(a.problem_id == attempt.problem_id and a.number == attempt.number
               for a in self._items.values()):
            raise ConcurrentModification("Attempt number already taken")
        self._items[attempt.id] = copy.deepcopy(attempt)

    def get(self, attempt_id: str) -> Attempt:
        try:
            return copy.deepcopy(self._items[attempt_id])
        except KeyError:
            raise NotFound(f"Attempt {attempt_id} not found") from None

    def save(self, attempt: Attempt) -> None:
        stored = self._items.get(attempt.id)
        if stored is None:
            raise NotFound(f"Attempt {attempt.id} not found")
        if stored.version != attempt.version:
            raise ConcurrentModification(f"Attempt {attempt.id} was modified by someone else")
        attempt.version += 1
        self._items[attempt.id] = copy.deepcopy(attempt)

    def list_for_problem(self, problem_id: str) -> list[Attempt]:
        items = [a for a in self._items.values() if a.problem_id == problem_id]
        return [copy.deepcopy(a) for a in sorted(items, key=lambda a: a.number)]

    def list_all(self) -> list[Attempt]:
        items = sorted(self._items.values(), key=lambda a: a.created_at, reverse=True)
        return [copy.deepcopy(a) for a in items]