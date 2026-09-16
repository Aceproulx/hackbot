---
name: frontend-design
description: Visual and UX decisions for new UI — typography, color, spacing, layout — so output doesn't read as a generic template. Use whenever generating new pages, components, or visual layouts.
---

## The default failure mode

Left unguided, generated UI converges on: centered card, generic blue
(#3B82F6-ish) accent, system-ui font stack, 16px/24px/32px spacing
grid, drop shadow on everything, rounded-lg on everything. It's not
wrong, it's just indistinguishable from every other generated UI.
Treat this as the floor, not the target.

## Make one real typographic decision

Pick a font pairing (or a single well-chosen typeface) that fits the
content's tone before writing markup — don't default to the platform
default and call it done. A finance dashboard, a kids' app, and a law
firm site should not share a type voice.

## Make one real color decision

Pick a palette with intent (a dominant, a supporting neutral scale,
one accent) rather than reaching for the first saturated blue/purple.
Write it down as CSS variables / design tokens up front and use only
those — don't sprinkle one-off hex values through the markup.

## Spacing and rhythm

Pick a spacing scale (e.g. 4px base, or an 8px base) and stick to it.
Inconsistent gaps (13px here, 18px there) are the single fastest
"AI-generated" tell.

## Content over placeholder

If the task gives enough context to write real copy (headlines, button
labels, empty states), write real copy. Lorem ipsum and "Lorem Company
Inc." placeholders read as unfinished.

## Icons, not emojis

Use real icons for all UI affordances — an icon set (Lucide, Heroicons,
etc.) or inline SVG — never emojis as icons. Emojis render
inconsistently across platforms, read as unfinished/placeholder, and
break once you need color, hover, or disabled states. Pick one icon set
and one stroke weight per project and keep it consistent. Emojis are
acceptable only in deliberately casual copy (e.g. a fun onboarding
line), never as functional UI icons.

## Checklist before calling a layout done

- Does this have a point of view, or could it be any SaaS landing page?
- Are colors/spacing coming from a small defined set of tokens, not
  ad hoc values scattered through the file?
- Would this still look intentional with the images/content removed
  (i.e. does the layout itself carry design, not just decoration)?
