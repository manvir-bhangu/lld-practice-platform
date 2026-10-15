from datetime import datetime, timedelta, timezone

import pytest

from app.domain.attempt import Attempt
from app.domain.content import TextDesign
from app.domain.enums import AttemptStatus
from app.domain.errors import ConcurrentModification, NotFound
from app.domain.feedback import CriterionFeedback, Evaluation
from app.repository.in_memory import InMemoryAttemptRepository
from app.repository.sqlite import SqliteAttemptRepository

BASE = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(params=["memory", "sqlite"])
def repo(request):
    if request.param == "memory":
        return InMemoryAttemptRepository()
    return SqliteAttemptRepository(":memory:")


def new_attempt(id="a1", problem="parking-lot", number=1):
    return Attempt(id=id, problem_id=problem, number=number,
                   created_at=BASE + timedelta(minutes=number))


def completed_attempt():
    a = new_attempt()
    a.save_draft(TextDesign(sections={"classes": "ParkingLot, Spot"}))
    a.submit()
    a.start_evaluation()
    fb = CriterionFeedback("classes", 4, 5, "has Spot", "no Vehicle", "add Vehicle", 0.8)
    a.complete([Evaluation("rule_based", (fb,), summary="ok")])
    return a


def test_roundtrip_preserves_everything(repo):
    original = completed_attempt()
    repo.add(original)
    loaded = repo.get("a1")
    assert loaded.status == AttemptStatus.COMPLETED
    assert loaded.content.sections == {"classes": "ParkingLot, Spot"}
    assert loaded.evaluations[0].summary == "ok"
    assert loaded.evaluations[0].feedback[0].suggestion == "add Vehicle"
    assert loaded.created_at == original.created_at
    assert loaded.submitted_at == original.submitted_at
    assert loaded.evaluation_started_at == original.evaluation_started_at

def test_get_missing_raises(repo):
    with pytest.raises(NotFound):
        repo.get("nope")


def test_get_returns_independent_copy(repo):
    repo.add(new_attempt())
    a = repo.get("a1")
    a.save_draft(TextDesign(sections={"classes": "changed"}))
    assert repo.get("a1").content is None


def test_save_increments_version(repo):
    repo.add(new_attempt())
    a = repo.get("a1")
    a.save_draft(TextDesign(sections={"classes": "X"}))
    repo.save(a)
    assert a.version == 1
    assert repo.get("a1").version == 1


def test_stale_save_rejected(repo):
    repo.add(new_attempt())
    first = repo.get("a1")
    second = repo.get("a1")
    first.save_draft(TextDesign(sections={"classes": "X"}))
    repo.save(first)
    second.save_draft(TextDesign(sections={"classes": "Y"}))
    with pytest.raises(ConcurrentModification):
        repo.save(second)
    assert repo.get("a1").content.sections == {"classes": "X"}


def test_save_unknown_attempt_raises_not_found(repo):
    with pytest.raises(NotFound):
        repo.save(new_attempt(id="ghost"))


def test_duplicate_attempt_number_rejected(repo):
    repo.add(new_attempt(id="a1", number=1))
    with pytest.raises(ConcurrentModification):
        repo.add(new_attempt(id="a2", number=1))


def test_same_number_allowed_for_different_problems(repo):
    repo.add(new_attempt(id="a1", problem="parking-lot", number=1))
    repo.add(new_attempt(id="a2", problem="elevator", number=1))


def test_list_for_problem_ordered_by_number(repo):
    repo.add(new_attempt(id="a2", number=2))
    repo.add(new_attempt(id="a1", number=1))
    repo.add(new_attempt(id="x", problem="elevator", number=1))
    assert [a.number for a in repo.list_for_problem("parking-lot")] == [1, 2]


def test_list_all_newest_first(repo):
    repo.add(new_attempt(id="a1", number=1))
    repo.add(new_attempt(id="a2", number=2))
    assert [a.id for a in repo.list_all()] == ["a2", "a1"]


def test_sqlite_persists_across_connections(tmp_path):
    path = str(tmp_path / "test.db")
    first = SqliteAttemptRepository(path)
    first.add(completed_attempt())
    first.close()
    second = SqliteAttemptRepository(path)
    assert second.get("a1").status == AttemptStatus.COMPLETED
    second.close()