"""Triage queue manager — terminal program for a hospital emergency unit.

Models a priority queue where patients are attended strictly by triage
level (1 = critical, 2 = urgent, 3 = standard) and, within the same
level, in arrival order (FIFO).

Standard library only. See DESIGN.md for the reasoning behind the
chosen data structure and the concurrency discussion.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Deque, Dict, List, Optional

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

TRIAGE_LEVELS = (1, 2, 3)
TRIAGE_LABELS = {1: "critical", 2: "urgent", 3: "standard"}


class TriageError(Exception):
    """Base class for triage queue errors."""


class EmptyQueueError(TriageError):
    """Raised when `dequeue` or `peek` is called on an empty queue."""


@dataclass(frozen=True)
class Patient:
    """A patient waiting to be attended.

    Attributes:
        name: The patient's name.
        triage_level: 1 (critical), 2 (urgent) or 3 (standard).
        arrived_at: When the patient was registered.
    """

    name: str
    triage_level: int
    arrived_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("patient name must be a non-empty string")
        if (
            not isinstance(self.triage_level, int)
            or isinstance(self.triage_level, bool)
            or self.triage_level not in TRIAGE_LEVELS
        ):
            raise ValueError(
                f"triage_level must be one of {list(TRIAGE_LEVELS)}, "
                f"got {self.triage_level!r}"
            )
        if not isinstance(self.arrived_at, datetime):
            raise ValueError("arrived_at must be a datetime")


class TriageQueue:
    """A priority queue of patients, backed by one FIFO line per triage level.

    Why three `deque`s (see DESIGN.md for the full discussion):

    * Enqueue is O(1): append to the right end of the patient's own line.
    * Peek/dequeue is O(1): serve the first non-empty line, starting with
      level 1, taking from the left.
    * A critical patient arriving late "jumps" the whole line without any
      re-sorting: level 1 is simply drained before levels 2 and 3.
    * FIFO within a level is the deque's natural append-right/pop-left.

    Every public operation takes the same `threading.Lock`, so a pop is
    atomic: two workers can never be handed the same patient.
    """

    def __init__(self) -> None:
        self._lines: Dict[int, Deque[Patient]] = {
            level: deque() for level in TRIAGE_LEVELS
        }
        self._lock = Lock()

    # -- core operations ---------------------------------------------------

    def enqueue(self, patient: Patient) -> None:
        """Add `patient` to the end of their triage level's line."""
        with self._lock:
            self._lines[patient.triage_level].append(patient)

    def dequeue(self) -> Patient:
        """Remove and return the next patient to be attended.

        Raises:
            EmptyQueueError: if no patients are waiting.
        """
        with self._lock:
            level = self._first_non_empty_level()
            if level is None:
                raise EmptyQueueError("no patients are waiting")
            return self._lines[level].popleft()

    def peek(self) -> Patient:
        """Return the next patient to be attended without removing them.

        Raises:
            EmptyQueueError: if no patients are waiting.
        """
        with self._lock:
            level = self._first_non_empty_level()
            if level is None:
                raise EmptyQueueError("no patients are waiting")
            return self._lines[level][0]

    def list_queue(self) -> List[Patient]:
        """Return all waiting patients in attention order (level, then FIFO)."""
        with self._lock:
            return [
                patient
                for level in TRIAGE_LEVELS
                for patient in self._lines[level]
            ]

    def stats(self) -> Dict[int, int]:
        """Return the number of waiting patients per triage level."""
        with self._lock:
            return {level: len(line) for level, line in self._lines.items()}

    def __len__(self) -> int:
        with self._lock:
            return sum(len(line) for line in self._lines.values())

    def __bool__(self) -> bool:
        return len(self) > 0

    # -- helpers -----------------------------------------------------------

    def _first_non_empty_level(self) -> Optional[int]:
        """Return the highest-priority triage level with patients, if any."""
        for level in TRIAGE_LEVELS:
            if self._lines[level]:
                return level
        return None


# ---------------------------------------------------------------------------
# Command-line interface
# ---------------------------------------------------------------------------

MENU = """\
  ----------------------------------------
  Emergency Unit - Triage Queue
  ----------------------------------------
  1. Register new patient
  2. Call next patient
  3. View queue
  4. View queue stats
  5. Exit
  ----------------------------------------"""


def main() -> None:
    """Run the interactive terminal menu until the user exits."""
    queue = TriageQueue()

    while True:
        print(MENU)
        choice = input("Choose an option (1-5): ").strip()

        if choice == "1":
            _register_patient(queue)
        elif choice == "2":
            _call_next_patient(queue)
        elif choice == "3":
            _view_queue(queue)
        elif choice == "4":
            _view_stats(queue)
        elif choice == "5":
            print("Goodbye.")
            return
        else:
            print(f"'{choice}' is not a valid option. Please choose 1-5.")
        print()


def _register_patient(queue: TriageQueue) -> None:
    name = input("Patient name: ").strip()
    if not name:
        print("Patient name cannot be empty.")
        return

    raw_level = input(
        "Triage level (1 = critical, 2 = urgent, 3 = standard): "
    ).strip()
    try:
        level = int(raw_level)
        patient = Patient(
            name=name, triage_level=level, arrived_at=datetime.now()
        )
    except ValueError as error:
        print(f"Could not register patient: {error}")
        return

    queue.enqueue(patient)
    print(f"Registered '{name}' as level {level} ({TRIAGE_LABELS[level]}).")


def _call_next_patient(queue: TriageQueue) -> None:
    try:
        patient = queue.dequeue()
    except EmptyQueueError:
        print("The queue is empty - nobody is waiting.")
        return

    wait = datetime.now() - patient.arrived_at
    print(
        f"Next patient: '{patient.name}' "
        f"(level {patient.triage_level}, {TRIAGE_LABELS[patient.triage_level]}), "
        f"arrived at {patient.arrived_at.strftime('%H:%M:%S')} "
        f"({_format_wait(wait)} waiting)."
    )


def _view_queue(queue: TriageQueue) -> None:
    waiting = queue.list_queue()
    if not waiting:
        print("The queue is empty.")
        return

    print(f"{'#':>4}  {'Level':<6} {'Name':<24} Arrived")
    print(f"{'-'*4}  {'-'*6} {'-'*24} {'-'*8}")
    for index, patient in enumerate(waiting, start=1):
        label = TRIAGE_LABELS[patient.triage_level]
        print(
            f"{index:>4}  {label:<6} {patient.name:<24} "
            f"{patient.arrived_at.strftime('%H:%M:%S')}"
        )
    first = waiting[0]
    print(f"Next up: '{first.name}' ({TRIAGE_LABELS[first.triage_level]}).")


def _view_stats(queue: TriageQueue) -> None:
    counts = queue.stats()
    print(f"Waiting patients: {sum(counts.values())}")
    for level in TRIAGE_LEVELS:
        print(f"  Level {level} ({TRIAGE_LABELS[level]}): {counts[level]}")


def _format_wait(wait: timedelta) -> str:
    total_seconds = int(wait.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}m {seconds:02d}s"


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print()
        print("Goodbye.")
