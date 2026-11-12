"""Unit tests for the triage queue (standard library `unittest`)."""

import unittest
from datetime import datetime, timedelta

from triage_queue import EmptyQueueError, Patient, TriageQueue

BASE = datetime(2026, 1, 1, 12, 0, 0)


def make_patient(name: str, level: int, arrival_offset: int = 0) -> Patient:
    """Build a patient who arrived `arrival_offset` seconds after BASE."""
    return Patient(
        name=name,
        triage_level=level,
        arrived_at=BASE + timedelta(seconds=arrival_offset),
    )


class TriageQueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = TriageQueue()

    # -- attention order -----------------------------------------------------

    def test_higher_level_served_first_regardless_of_arrival(self):
        self.queue.enqueue(make_patient("Standard", 3, arrival_offset=0))
        self.queue.enqueue(make_patient("Urgent", 2, arrival_offset=10))
        self.queue.enqueue(make_patient("Critical", 1, arrival_offset=20))

        names = [self.queue.dequeue().name for _ in range(3)]
        self.assertEqual(names, ["Critical", "Urgent", "Standard"])

    def test_same_level_served_in_arrival_order(self):
        self.queue.enqueue(make_patient("First", 2, arrival_offset=0))
        self.queue.enqueue(make_patient("Second", 2, arrival_offset=1))
        self.queue.enqueue(make_patient("Third", 2, arrival_offset=2))

        names = [self.queue.dequeue().name for _ in range(3)]
        self.assertEqual(names, ["First", "Second", "Third"])

    def test_critical_patient_joining_late_jumps_the_line(self):
        self.queue.enqueue(make_patient("Urgent", 2, arrival_offset=0))
        self.queue.enqueue(make_patient("Standard", 3, arrival_offset=1))
        self.queue.enqueue(make_patient("Critical", 1, arrival_offset=999))

        self.assertEqual(self.queue.peek().name, "Critical")

    def test_list_queue_returns_attention_order(self):
        self.queue.enqueue(make_patient("Standard", 3))
        self.queue.enqueue(make_patient("Critical", 1))
        self.queue.enqueue(make_patient("Urgent", 2))

        names = [patient.name for patient in self.queue.list_queue()]
        self.assertEqual(names, ["Critical", "Urgent", "Standard"])

    # -- peek ------------------------------------------------------------------

    def test_peek_does_not_remove_patient(self):
        self.queue.enqueue(make_patient("Critical", 1))

        self.assertEqual(self.queue.peek().name, "Critical")
        self.assertEqual(len(self.queue), 1)

    # -- empty queue ------------------------------------------------------------

    def test_dequeue_on_empty_queue_raises(self):
        with self.assertRaises(EmptyQueueError):
            self.queue.dequeue()

    def test_peek_on_empty_queue_raises(self):
        with self.assertRaises(EmptyQueueError):
            self.queue.peek()

    def test_list_queue_on_empty_queue_is_empty_list(self):
        self.assertEqual(self.queue.list_queue(), [])

    # -- stats -------------------------------------------------------------------

    def test_stats_counts_per_level(self):
        self.queue.enqueue(make_patient("A", 1))
        self.queue.enqueue(make_patient("B", 2))
        self.queue.enqueue(make_patient("C", 2))
        self.queue.enqueue(make_patient("D", 3))

        self.assertEqual(self.queue.stats(), {1: 1, 2: 2, 3: 1})
        self.assertEqual(len(self.queue), 4)

    def test_stats_are_zero_on_empty_queue(self):
        self.assertEqual(self.queue.stats(), {1: 0, 2: 0, 3: 0})

    # -- validation -----------------------------------------------------------------

    def test_rejects_invalid_triage_level(self):
        with self.assertRaises(ValueError):
            Patient(name="X", triage_level=4, arrived_at=BASE)
        with self.assertRaises(ValueError):
            Patient(name="X", triage_level="1", arrived_at=BASE)

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            Patient(name="   ", triage_level=1, arrived_at=BASE)


if __name__ == "__main__":
    unittest.main()
