---
name: component-patterns
description: Conventions for recurring UI pieces (forms, nav, cards, modals, tables) so components stay consistent within a project. Use when a task involves building or extending reusable components.
---

## Before adding a new component

Check whether an equivalent already exists in the project (grep for
similar names/patterns) before writing a new one from scratch.
Duplicated near-identical components are the top source of drift in
generated codebases.

## Forms

- Controlled inputs, single source of truth for form state.
- Validate on submit at minimum; inline validation only if the task
  calls for it — don't add complexity that wasn't asked for.
- Always handle: empty state, submitting state (disable the submit
  button), success, and error — don't leave error handling as a TODO.

## Navigation

- One nav pattern per project. If a project already has a nav
  component, extend it — don't create a second competing one.
- Active-route styling should be handled in one place, not duplicated
  per link.

## Cards / lists

- Separate the data-shape (what a "card" needs) from the presentation.
  A `Card` component should take props, not reach into global state.
- Handle the empty-list case explicitly — an empty `<div>` is not a
  design.

## Modals / dialogs

- One modal/dialog primitive per project, reused with different
  content, not five bespoke modal implementations.
- Always wire up: close on backdrop click, close on Escape, and focus
  management — these get skipped and are the most common accessibility
  miss.

## Naming and structure

- Match whatever convention the project already uses for file
  structure and naming (check a couple of existing files before
  guessing). Don't introduce a second convention mid-project.
