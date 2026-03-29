---
name: audit-report-refresh
description: Refresh an existing audit report against the latest code while preserving the parts of the report structure that are still useful. Use when the user asks to redo an audit, run a second or third audit pass, update a previous report, fix inaccuracies in an existing audit document, or keep a strong prior report structure while replacing stale conclusions with code-grounded findings.
---

# Audit Report Refresh

Use this skill when there is already an audit report or module document and the user wants a new pass based on the latest code.

If there is no prior report and the task is a fresh audit, prefer `system-audit-report`.

If the redesign introduced complicated runtime paths, async jobs, or reconcile loops, pair this skill with `architecture-data-flow-trace`.

## Goal

Keep the good parts of the previous report:

- structure
- section ordering
- useful framing
- strong explanations

Replace the bad parts:

- stale facts
- outdated conclusions
- missing deltas
- gaps that the new code now closes

## Core Rules

1. Sync to the latest code before comparing anything.
2. Treat the previous report as input material, not truth.
3. Explicitly identify what changed since the previous report.
4. Re-audit the subsystem from code; do not “patch” the old report blindly.
5. Preserve strong structure when it still helps the reader.

## Required Workflow

### 1. Read the Existing Report First

Extract:

- the current section structure
- strong sections worth preserving
- explicit prior conclusions
- prior blocker list
- known assumptions

### 2. Rebuild the Current Picture from Code

Audit the latest implementation using the same standards as `system-audit-report`:

- models
- services
- APIs
- migrations
- tasks
- tests
- UI if relevant

### 3. Compare Old Conclusions vs. Current Reality

Classify major conclusions into:

- still correct
- partially correct
- now outdated
- reversed by new code
- still unresolved

This comparison should appear in the refreshed report, usually near the beginning.

### 4. Rewrite, Do Not Merely Edit

When a section is materially outdated:

- rewrite it from current code

When a section is structurally strong but factually stale:

- preserve the section shape
- replace the content

When a prior conclusion is now wrong:

- say so explicitly and state what changed in the code

## Required Additions in the Refreshed Report

The refreshed report should usually add:

1. current code baseline
2. what changed since the previous audit
3. which old blockers were fixed
4. which old blockers remain
5. any new defects introduced by the redesign

## Quality Bar

A good refresh report makes it easy to answer:

- What did we think last time?
- What is true now?
- What got better?
- What is still risky?
- What new problems appeared after the redesign?

## Validation

At minimum:

- run `git diff --check`

If possible, run representative tests around the redesigned area and say whether the new conclusions are supported by passing tests.

## Do Not

- Do not copy old conclusions forward without re-verifying them.
- Do not keep wording that implies old architecture still exists.
- Do not preserve structure at the cost of factual accuracy.
