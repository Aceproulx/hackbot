---
name: sandwich-attack-token-bruteforce
description: >
  Use this skill during authorized bug bounty / pentest recon whenever a target issues a security-sensitive token (password-reset token, invite token, email-verification token, API key) as a UUID — especially if you can get the application to hand you one on demand (e.g. by triggering your own password reset). Covers detecting a UUIDv1 (timestamp + clock-sequence + MAC/node-ID based, NOT random UUIDv4), and the "Sandwich Attack": bracketing a victim's token between two attacker-controlled tokens generated immediately before/after the victim's, deriving the narrow timestamp window and shared node-ID/clock-sequence, and brute-forcing every candidate UUID in that window against the token-consuming endpoint (e.g. with ffuf) for zero-click account takeover. Trigger on requests to test password-reset flows, invite/verification links, or "is this token guessable" — always only against in-scope targets and your own test accounts.
metadata:
  source: https://www.landh.tech/blog/20230811-sandwich-attack/
---

# Sandwich Attack: Brute-forcing UUIDv1 Security Tokens

From Roni Carta / Lupin-Holmes (Depi/LupinHolmes research, presented at HacktivityCon 2022). Targets applications that use a UUID as a password-reset (or similar) token under the mistaken assumption that "it's a UUID, so it's unguessable." That assumption only holds for UUIDv4 (random). UUIDv1 is timestamp + MAC-address based and is a brute-forceable *range*, not a random value.

Only run this against in-scope targets, and only ever complete the takeover against an account you control (your own second test account) — brute-forcing a real victim's session is the line between PoC and abuse.

## Step 1: Confirm it's UUIDv1

Grab any token the app hands you (e.g. trigger your own password reset) and check its version nibble. A UUID is laid out as:
```
xxxxxxxx-xxxx-Vxxx-xxxx-xxxxxxxxxxxx
             ^-- version nibble
```
`V=1` confirms UUIDv1 (timestamp + node ID). `V=4` means random — not brute-forceable this way, stop here.

UUIDv1's six fields: `time_low-time_mid-time_hi_and_version-clock_seq-node`. `time_low`, `time_mid`, and the low 12 bits of `time_hi_and_version` combine into a 60-bit timestamp (100-nanosecond intervals since 1582-10-15, the Gregorian/Julian calendar epoch UUIDs use — subtract the epoch offset and divide by 10,000,000 to get a Unix timestamp). `node` is meant to be the generating machine's MAC address, and `clock_seq` is a counter that resets/increments per generator process.

**Key exploitable property:** if two UUIDs are generated back-to-back on the *same machine*, `node` and usually `clock_seq` stay identical, and the timestamp portion differs by only a small delta. That turns "guess a random 122-bit value" into "guess a timestamp within a known narrow window, holding node/clock_seq fixed."

## Step 2: Build the sandwich

1. Trigger a token for **your own account** (slice of bread #1) — capture the full UUID and note the time you requested it.
2. Trigger a token for the **victim's account** (the filling) — you need the app to let you do this without the victim's interaction (e.g. an unauthenticated "forgot password" that only needs an email/username, no confirmation).
3. Immediately trigger **another token for your own account** (slice of bread #2).

You now have two known UUIDs (yours) that bracket the unknown victim UUID in time. Decode all three timestamps; the victim's token's timestamp — and therefore its full UUID — must fall between your two bracketing values.

## Step 3: Generate every candidate in the window

Use [Lupin-Holmes/sandwich](https://github.com/Lupin-Holmes/sandwich) (or write an equivalent script) to enumerate every valid UUIDv1 between your two bracketing timestamps, holding `node` and `clock_seq` at the observed value(s). Note the resulting candidate count — the original write-up saw ~100,000 candidates for a tight bracket window, which is a very feasible fuzz size.

**Multiple generating machines:** before assuming a single `node`/`clock_seq` pair, fire several reset requests in a row (the original research used 30) and inventory the distinct `(node, clock_seq)` pairs you observe. If the app is load-balanced across N machines generating tokens, you need to generate the candidate set for *each* observed pair — this multiplies your brute-force space by N, but is still tractable.

## Step 4: Fuzz the token-consuming endpoint

Feed the generated candidate list into a fast fuzzer (e.g. [ffuf](https://github.com/ffuf/ffuf)) against the actual reset-token-consuming endpoint (the "set new password" request), watching for a response that differs from the "invalid/expired token" baseline (status code, body length, redirect target). A hit means you've found the victim's real token — complete the flow (set a new password) only against your own bracketed test account to prove impact; do not do this against a real victim account in a live program.

## Reporting checklist

- The decoded UUIDv1 fields showing timestamp, node ID, and clock sequence, and how you derived the Gregorian/Julian offset math.
- The bracket window size (candidate count) and how many generating machines/node-IDs you observed.
- The fuzzer run against your own bracketed test token as PoC (never a real victim).
- Recommend the fix: switch to UUIDv4 or a CSPRNG-backed opaque token, not a "looks random" UUID variant.
