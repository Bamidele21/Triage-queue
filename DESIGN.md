# Design notes

Companion document to `triage_queue.py`. The spec asked for two things
explained here: the choice of internal data structure, and how concurrent
access (two workers at once) is kept safe.

## 1. Data structure: one FIFO line per triage level

`TriageQueue` holds three `collections.deque`s, one per triage level
(1 = critical, 2 = urgent, 3 = standard).

- **Enqueue** — append to the right end of the patient's own line: O(1).
- **Peek / dequeue** — serve the first non-empty line in level order
  (1 → 2 → 3), taking from the left: O(1).
- **Late critical patient** — a level-1 patient who arrives while levels 2
  and 3 are full goes straight to the front of the *next call* simply
  because the dispatcher drains level 1 before looking anywhere else.
  Nothing is re-sorted and nothing is shifted: the invariant is
  "always serve the highest-priority non-empty line first".
- **FIFO within a level** — falls out of the deque's natural
  append-right / pop-left behaviour.

### Alternatives considered

| Structure | enqueue | dequeue | Why it was rejected |
| --- | --- | --- | --- |
| Single `deque` | O(n) | O(n) | Has no priority concept. To respect triage you must scan to find the insertion point and shift elements, or re-sort on every insert — exactly what the spec warns against. |
| Sorted `list` | O(n) | O(n) | Inserting at the right position shifts half the list on average; popping the front shifts everything again. |
| `heapq` min-heap of `(level, arrival_seq, patient)` tuples | O(log n) | O(log n) | A real, classic solution — it was the runner-up. Rejected only because the triage levels are a small, fixed set: three deques are simpler to read and debug, keep FIFO explicit instead of encoded in a sequence counter, and give O(1) on both hot paths. `list_queue()` also becomes trivial (concatenate three lines) instead of requiring a heap pass. |

Either `heapq` or the three-line design is defensible; the three-line
design was chosen for clarity and O(1) operations.

## 2. Concurrent workers: preventing double-processing

Scenario from the spec: worker A dequeues at the same moment worker B
enqueues a new critical patient — and, worse, two workers may both try to
dequeue at once and attend the same patient.

The rule that prevents double-processing: **remove first, then process,
and make the remove atomic.**

1. `TriageQueue` guards every operation with a single `threading.Lock`.
   The check-and-remove inside `dequeue()` is therefore atomic: at most
   one worker can pop at a time, and the patient is out of the queue
   before the worker starts attending them. "Calling a patient" and
   "removing them from the board" are one indivisible step, so two
   workers can never be handed the same patient.
2. The state mutation order is: pop → (queue no longer contains the
   patient) → attend. If a worker crashed mid-attendance, the patient
   would need a recovery path (re-enqueue at the *front* of their level's
   line); the opposite order — attend first, remove afterwards — lets two
   workers treat the same patient simultaneously.
3. The enqueue-vs-dequeue race is harmless by construction. If the
   critical patient is enqueued before worker A's pop completes, the pop
   returns the critical patient. If the enqueue lands a moment after,
   worker A keeps the patient they already own (it was removed first)
   and the critical patient leads the next call. Either way, no patient
   is lost and none is processed twice.
4. `peek()` is advisory only: it is used for display, never as a
   "reserve" step before processing. The only way to claim a patient is
   the atomic `dequeue()`. Between a peek and a dequeue the queue may
   have changed, and that is fine because a claim is never based on a
   stale peek.

With a single lock and no operation that acquires more than one lock,
there is no lock-ordering question and no deadlock. A production system
would additionally make the queue persistent and re-enqueue patients
whose worker failed before attendance; both are out of scope here.
