---
name: architecture-data-flow-trace
description: Trace the real runtime architecture and data flow of a subsystem from the current code. Use when the user asks to map request flow, state transitions, background jobs, repair loops, read paths, sequence diagrams, or explain how data moves through the system end to end.
---

# Architecture Data Flow Trace

Use this skill when the main task is to explain how a subsystem actually runs, not just what files exist.

This skill is especially useful as support for `system-audit-report` and `audit-report-refresh` when the subsystem has multiple entrypoints, asynchronous jobs, or eventual-consistency behavior.

## Goal

Produce a runtime map of the subsystem that makes these questions easy to answer:

- where requests or events enter
- how state changes over time
- where data is persisted
- which background jobs or watchers participate
- how drift is repaired
- how results become visible to users

## Core Rules

1. Trace from the current code, not from docs or assumptions.
2. Follow real execution paths across layers:
   - API
   - service
   - model
   - task / worker
   - external system integration
   - user-visible read path
3. Distinguish direct evidence from inferred behavior.
4. Keep the trace end-to-end; do not stop at the first request handler.
5. Call out broken or missing edges explicitly.

## Required Workflow

### 1. Lock the Trace Baseline

Record:

- trace date
- current branch
- commit hash
- subsystem being traced

### 2. Define the Trace Slices

Break the subsystem into a few concrete flows, for example:

- create
- update
- consume
- enforce
- reconcile
- delete

If the subsystem is large, trace the most important flows first instead of trying to describe everything at once.

### 3. Find the Entrypoints

Use `rg` to identify where each flow starts:

- API routes
- CLI commands
- webhooks
- cron jobs
- watch loops
- signal handlers
- event consumers

List the concrete functions or classes that receive the first input.

### 4. Follow the Write Path

For each flow, identify:

1. the first orchestrating function
2. downstream service calls
3. database writes
4. side effects in external systems
5. emitted follow-up work

Be explicit about ordering, especially when state is committed before external calls or vice versa.

### 5. Follow the Async and Repair Paths

Do not stop after the synchronous request path.

Trace:

- scheduled jobs
- task runners
- reconcile loops
- best-effort repair paths
- cleanup or compensation logic
- watchdogs and auto-stop logic

If consistency depends on a later job, say so.

### 6. Follow the Read Path

Identify how the final state becomes visible:

- API read endpoints
- admin endpoints
- UI pages
- derived summary functions
- cached views or aggregates

Call out where the read model differs from the write model.

### 7. Identify State Boundaries and Invariants

For each major entity, capture:

- authoritative store
- derived stores
- active versus terminal states
- expected invariants
- likely drift points

Good traces usually include a small state transition table when the subsystem is stateful.

### 8. Produce Trace Artifacts

The output should usually include:

1. a high-level architecture map
2. one or more flow descriptions
3. a state transition table when relevant
4. a data ownership table
5. a drift / repair section
6. Mermaid sequence or flow diagrams when they materially help

## Quality Bar

A strong trace should answer:

- What starts the flow?
- Which function owns orchestration?
- Which writes are authoritative?
- Which later jobs modify or repair the state?
- Where can the system become temporarily inconsistent?
- Which path determines what the user actually sees?

## Common Failure Modes to Avoid

- Listing files without tracing execution
- Treating background jobs as optional when they close the loop
- Ignoring delete and cleanup paths
- Confusing intended architecture with running code
- Omitting read paths and only documenting writes

## Validation

For docs-only changes:

- run `git diff --check`

If the trace is part of a larger audit and representative tests exist, note which flows those tests actually cover.
