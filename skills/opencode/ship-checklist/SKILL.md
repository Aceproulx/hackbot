---
name: ship-checklist
description: Pre-handoff pass to run before declaring a build finished — responsiveness, accessibility, empty/error/loading states, basic perf. Use at the end of any non-trivial build task.
---

## Run this before saying "done"

**Responsive**
- Does it hold up narrow (mobile width) and wide (desktop)? Check the
  layout doesn't just break at some untested middle width.

**States**
- Loading state exists for anything async.
- Empty state exists for anything list/data-driven (not just "nothing
  renders").
- Error state exists for anything that can fail (network calls, form
  submission) — not a silent failure.

**Accessibility basics**
- Interactive elements are real buttons/links, not clickable `<div>`s.
- Images have alt text (or explicitly empty alt for decorative ones).
- Color contrast is plausible for body text against its background.
- Focus is visible and keyboard-navigable for anything interactive
  (modals, menus, forms).

**Perf basics**
- No obviously unbounded re-renders (state updates in render body,
  missing dependency arrays causing loops).
- Large lists aren't rendering hundreds of DOM nodes with no
  windowing/pagination when that matters.

**Content**
- No leftover placeholder/lorem-ipsum text, "TODO" comments in
  user-facing copy, or console.log debug statements.

## What NOT to do

Don't turn this into a blocking gate that stalls delivery — it's a
fast self-review pass, not a formal QA cycle. Note anything you
deliberately skipped (e.g. "didn't add pagination since list is
capped at 20 items") rather than silently leaving it out.
