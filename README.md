# Triage Queue

A terminal-based priority queue manager for a hospital emergency unit,
built from the `triage-criteria.md` spec. Python standard library only —
no external packages.

## How it works

Patients are registered with a triage level and attended in this order:

1. **Level 1 — critical** (always first)
2. **Level 2 — urgent**
3. **Level 3 — standard**

Within the same level, patients are seen in arrival order (FIFO).
See `DESIGN.md` for the data-structure reasoning and concurrency notes.

## Running it

```bash
python triage_queue.py
```

The menu lets you register a patient, call the next patient, view the
queue, and see per-level stats.

## Running the tests

```bash
python -m unittest -v
```
