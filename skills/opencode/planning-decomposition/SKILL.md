---
name: planning-decomposition
description: How to break a build request into a short plan before writing code. Use for any new page, feature, or app — skip for one-line fixes or single-prop tweaks.
---

## When this applies

Trigger on: "build me a...", "create a...", "make an app that...",
anything spanning multiple components/files, anything with unclear
data flow. Do NOT trigger for: single bug fixes, one-property style
changes, renaming, adding one field to an existing form.

## The decomposition

For a qualifying request, produce (in your head or as a short written
note, not a novel):

1. **Surface** — what screens/components exist, one line each.
2. **Data** — what state exists, where it lives (local component
   state vs. shared/global), what shape it's in. This is the part
   people skip and regret; get it right before touching JSX/HTML.
3. **Interactions** — the 2-4 things a user actually does (submit
   form, filter list, toggle view). Everything else is decoration.
4. **Build order** — structure/routing → core interaction working
   with placeholder styling → visual pass → edge states (empty,
   loading, error).

## Anti-patterns to avoid

- Writing 500 lines of one component before checking it renders.
- Designing the visual system before the data shape is settled —
  you'll redo the layout once you know what's actually being shown.
- Treating every request as needing full step 1-4 ceremony. A
  three-field contact form doesn't need a data-flow diagram.

## Output habit

State the plan in 3-6 short lines max before building, so the person
can course-correct cheaply, then build without waiting for a reply
unless something is genuinely architecture-blocking.
