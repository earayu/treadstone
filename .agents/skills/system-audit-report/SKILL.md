---
name: system-audit-report
description: Produce a code-grounded audit report for any subsystem in this repository. Use when the user asks to audit a system, explain how it works in detail, review data flow or architecture, assess whether it is production-ready, compare implementation against docs, or generate a detailed report based on the current code rather than assumptions.
---

# System Audit Report

Use this skill when the user wants a detailed, code-based audit of a subsystem, not a lightweight explanation.

If the user already has an audit report and wants it updated against the latest code while preserving the existing structure, prefer `audit-report-refresh`.

If the hardest part of the task is reconstructing runtime architecture or end-to-end flow, pair this skill with `architecture-data-flow-trace`.

## Output Standard

The deliverable is an audit report, not a generic overview. It must:

- be grounded in the current code
- distinguish facts from inferences
- identify defects, risks, and missing coverage
- judge whether the system is closed-loop and fit for launch

## Core Rules

1. Sync to the latest code before auditing.
2. Treat the current code as the source of truth.
3. Use existing docs, plans, and PR context only as references.
4. Every important conclusion should be backed by evidence:
   - file
   - function
   - API
   - migration
   - test
   - UI code
5. Do not stop at “what exists”; also evaluate:
   - what is partial
   - what is inconsistent
   - what is untested
   - what would block launch

## Required Workflow

### 1. Lock the Code Baseline

Record:

- audit date
- current branch
- commit hash
- audit scope

### 2. Gather the System Map

Read the smallest set of files that explains the subsystem end to end:

- current docs for the subsystem
- models
- services
- API routers
- schemas / serializers
- migrations
- scheduled tasks / watchers / reconcile loops
- tests
- relevant frontend pages if user-facing

Prefer `rg` to build the map before opening files.

### 3. Trace the Real Runtime Paths

For each major capability, identify:

- request path entrypoints
- service-layer orchestration
- database writes
- background task participation
- watch / reconcile / repair behavior
- user-visible read path

Pay special attention to:

- partial implementations
- config-gated enforcement
- best-effort code paths
- eventual consistency
- concurrency risks

### 4. Check the Closed Loops

For every important mechanism, verify the whole loop:

1. where data is created
2. how it is updated
3. how it is consumed
4. how limits are enforced
5. how failures are repaired
6. whether tests cover the path

If a loop is broken, say exactly where.

### 5. Compare Code vs. Existing Docs

If there is an existing design doc or module doc:

- preserve useful framing and structure
- replace stale facts
- call out meaningful deltas from the previous understanding

Never let older docs override the code.

## Required Report Structure

The report should usually include:

1. Audit metadata
2. Sources reviewed
3. Executive summary
4. Current-state status table
5. System goal and scope
6. Architecture and data flow
7. Data model and key tables
8. Runtime flow and background jobs
9. Key functions and interfaces
10. Enforcement and failure handling
11. Test coverage and gaps
12. Defects, risks, and improvement opportunities
13. Launch-readiness conclusion

Use Mermaid when a flow or architecture diagram would materially help.

## Quality Bar

A good audit report should answer all of these:

- What exactly does the system do today?
- What data model does it use?
- What triggers the core state transitions?
- What is real and running versus planned or stale?
- Where can the system drift or break?
- What has test coverage, and what does not?
- Is it suitable for launch, and under what claims?

## Validation

For docs-only changes:

- run `git diff --check`

If feasible, run representative tests for the audited subsystem and report:

- what was run
- what passed
- what was not run

## Do Not

- Do not rely on memory over code.
- Do not write vague statements like “the system seems robust”.
- Do not bury the key risks deep in the document.
- Do not equate the existence of tests with full reliability.
