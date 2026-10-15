import json
import sqlite3
import threading
from datetime import datetime

from app.domain.attempt import Attempt
from app.domain.content import content_from_dict
from app.domain.enums import AttemptStatus
from app.domain.errors import ConcurrentModification, NotFound
from app.repository.base import AttemptRepository
from app.repository.serialization import evaluations_from_json, evaluations_to_json

SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    problem_id TEXT NOT NULL,
    number INTEGER NOT NULL,
    status TEXT NOT NULL,
    content_json TEXT,
    evaluations_json TEXT NOT NULL DEFAULT '[]',
    failure_reason TEXT,
    created_at TEXT NOT NULL,
    submitted_at TEXT,
    evaluation_started_at TEXT,
    version INTEGER NOT NULL DEFAULT 0,
    UNIQUE (problem_id, number)
);
CREATE INDEX IF NOT EXISTS idx_attempts_problem ON attempts(problem_id);
"""


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _content_json(attempt: Attempt) -> str | None:
    return json.dumps(attempt.content.to_dict()) if attempt.content else None


def _row_to_attempt(row: sqlite3.Row) -> Attempt:
    content = json.loads(row["content_json"]) if row["content_json"] else None
    return Attempt(
        id=row["id"],
        problem_id=row["problem_id"],
        number=row["number"],
        status=AttemptStatus(row["status"]),
        content=content_from_dict(content) if content else None,
        evaluations=evaluations_from_json(row["evaluations_json"]),
        failure_reason=row["failure_reason"],
        created_at=datetime.fromisoformat(row["created_at"]),
        submitted_at=_parse(row["submitted_at"]),
        evaluation_started_at=_parse(row["evaluation_started_at"]),
        version=row["version"],
    )


class SqliteAttemptRepository(AttemptRepository):
    def __init__(self, path: str = "lld_practice.db"):
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def add(self, attempt: Attempt) -> None:
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO attempts (id, problem_id, number, status, content_json, "
                    "evaluations_json, failure_reason, created_at, submitted_at, "
                    "evaluation_started_at, version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        attempt.id, attempt.problem_id, attempt.number, attempt.status.value,
                        _content_json(attempt), evaluations_to_json(attempt.evaluations),
                        attempt.failure_reason, attempt.created_at.isoformat(),
                        _iso(attempt.submitted_at), _iso(attempt.evaluation_started_at),
                        attempt.version,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConcurrentModification("Attempt already exists or number taken") from exc

    def get(self, attempt_id: str) -> Attempt:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM attempts WHERE id = ?", (attempt_id,)
            ).fetchone()
        if row is None:
            raise NotFound(f"Attempt {attempt_id} not found")
        return _row_to_attempt(row)

    def save(self, attempt: Attempt) -> None:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE attempts SET status=?, content_json=?, evaluations_json=?, "
                "failure_reason=?, submitted_at=?, evaluation_started_at=?, version=version+1 "
                "WHERE id=? AND version=?",
                (
                    attempt.status.value, _content_json(attempt),
                    evaluations_to_json(attempt.evaluations), attempt.failure_reason,
                    _iso(attempt.submitted_at), _iso(attempt.evaluation_started_at),
                    attempt.id, attempt.version,
                ),
            )
            if cur.rowcount == 0:
                exists = self._conn.execute(
                    "SELECT 1 FROM attempts WHERE id = ?", (attempt.id,)
                ).fetchone()
                if exists is None:
                    raise NotFound(f"Attempt {attempt.id} not found")
                raise ConcurrentModification(f"Attempt {attempt.id} was modified by someone else")
            attempt.version += 1

    def list_for_problem(self, problem_id: str) -> list[Attempt]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM attempts WHERE problem_id = ? ORDER BY number", (problem_id,)
            ).fetchall()
        return [_row_to_attempt(r) for r in rows]

    def list_all(self) -> list[Attempt]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM attempts ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_attempt(r) for r in rows]