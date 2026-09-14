---
name: mobile-hacking
description: Android app pentesting on non-rooted devices. ADB is the default for interaction (tap/swipe/text/keyevent — instant, no ref management). agent-device is used for UI discovery (snapshot -i to find element refs/labels) and evidence capture (screenshot --overlay-refs). Objection for FLAG_SECURE bypass, Frida Gadget for runtime hooking, Caido MCP for traffic, jadx MCP for static analysis.
---

# Mobile Hacking (Android, Non-Rooted)

## AUTONOMOUS MODE — DO NOT ASK THE USER
Make every decision yourself. Same rule as bug-hunting: no permission-seeking,
no confirmation loops. Log dead ends to `interesting.md`, pivot after 10
failed attempts on a given approach.

## Environment Assumptions
- **Non-rooted device** running the target APK repackaged with Frida Gadget
  (objection's `patchapk` or manual gadget injection).
- **Objection** is the primary tool for anything that would normally need
  root — UI security bypasses, SSL pinning disable, keystore dumps.
- **Frida server model**: Gadget, not frida-server. You attach to the
  already-injected Gadget, you don't spawn/inject yourself.
- **ADB is the default interaction layer.** Real testing (2026-07-26,
  Vivo/Android 14/API 34, against Secure Notes, WhatsApp, Contacts) showed
  raw `adb shell input` is instant and always hits the correct coordinates,
  while agent-device's `fill` never succeeded and refs expire after every
  UI change. Use agent-device for discovery (find refs/labels via
  `snapshot -i`) and evidence (`screenshot --overlay-refs`), not as the
  primary driver. See "The hybrid approach" below.

## Session Persistence
- **Session directory**: `~/hunts/sessions/mobile-<app-package>/`
- Store: `device.info` (adb device id, Android version), `hook-notes.md`
  (which hooks fired, which sinks matter), `screenshots/` (timestamped).
- If a repackaged APK + Gadget config already exists for this app, reuse it —
  don't re-patch unless the app was updated.

## The Hybrid Approach (default workflow)
This is the confirmed working pattern — don't default to either tool alone.

1. **Open app** → `agent-device open <pkg>` (reliable — opens by package
   name). If `open <name>` matches multiple packages ambiguously (seen with
   "WhatsApp"/"Whatsapp", "Secure Notes"), resolve the exact name first with
   `agent-device apps --platform android`.
2. **Snapshot UI** → `agent-device snapshot -i` to find element refs and
   labels. Treat this as read-only discovery, not a driver of taps.
3. **Navigate/scroll** → `adb shell input tap <x> <y>` /
   `adb shell input swipe <x1> <y1> <x2> <y2> <ms>`
4. **Type text** → `adb shell input text "some%sstring"` (`%s` for spaces —
   confirmed reliable, unlike `agent-device fill` which timed out in every
   test).
5. **Send/submit** → `adb shell input tap <coords>` — don't assume
   `keyevent 66` (ENTER) submits; confirmed it does **not** send on
   WhatsApp's current version. Verify per-app before relying on it.
6. **Long-press** → `adb shell input swipe <x> <y> <x> <y> 800` (same
   start/end coords, ~800ms duration = long-press, not a drag).
7. **Tap menu buttons / confirm dialogs** → `agent-device press @ref` is
   fine here, since these are short-lived popups right after a fresh
   snapshot — take the snapshot immediately before pressing.
8. **Evidence** → `agent-device screenshot` (`--overlay-refs` for writeups —
   burns in @eN refs on the image, good for reports).

## agent-device — Discovery & Evidence Only
Confirmed reliable for:
- `open <package>` — opens any app by exact package name.
- `snapshot -i` — quick UI structure, ~2-3s latency (p95 ~3.4s — factor this
  into timing, not something to spam per-action).
- `screenshot --overlay-refs` — burns in refs, best tool for writeup
  evidence.
- `find "label" click` / `press @ref` — fine for short-lived popups/menus
  when the ref is fresh (snapshot taken immediately before).

Confirmed unreliable — do not rely on these:
- **`fill @ref`** — never succeeded in testing, times out. Use
  `adb shell input text` instead.
- **Ref expiry** — a ref goes stale after *any* UI change, not just screen
  navigation. Don't chain multiple `press @ref` calls off one snapshot;
  re-snapshot before each one if the UI could have shifted.
- **Sparse snapshots miss visible text** — confirmed a visible on-screen
  flag string was absent from `snapshot -i` output. If text you can see in
  a screenshot doesn't show up in the snapshot, fall back to reading it off
  a screenshot directly (visual inspection) rather than trusting the
  snapshot is complete.
- **Multi-step flows are tedious via agent-device alone** — tap → type →
  tap-send needs 3+ snapshots with sleeps between each if driven purely
  through refs. Use ADB for the tap/type/send chain instead (step 3-6 above).

## Raw ADB — Default Interaction
```bash
adb devices                                  # confirm device connected
adb shell wm size                            # screen dimensions, for coord taps
adb exec-out screencap -p > screenshots/$(date +%s).png
adb shell input tap <x> <y>
adb shell input swipe <x1> <y1> <x2> <y2> <ms>
adb shell input text "some%sstring"          # %s for spaces
adb shell input keyevent 66                  # ENTER — verify per-app, doesn't always submit
adb shell input keyevent 4                   # BACK
adb shell input keyevent 3                   # HOME
adb shell input keyevent 111                 # ESC
```

- **Finding coordinates**: use `agent-device snapshot -i` for labels/rough
  layout, then confirm exact tap targets against a fresh screenshot
  (`adb exec-out screencap -p` or `agent-device screenshot`) rather than
  guessing pixels blind.
- **uiautomator dump** as a secondary coordinate source if needed:
  ```bash
  adb shell uiautomator dump /sdcard/ui.xml
  adb pull /sdcard/ui.xml
  ```
  Parse the XML for the target element's `bounds="[x1,y1][x2,y2]"` and tap
  the center point.
- **Scripted flows**: chain tap/swipe/text sequences into a shell script per
  app flow (login, checkout, settings nav) so repeated testing runs (e.g.
  re-triggering a race condition or re-testing after a hook change) don't
  require manual re-navigation every time.
- **Exported component / activity launch**:
  ```bash
  adb shell am start -n <package>/<exported.activity>
  ```

## FLAG_SECURE Bypass — Objection (Non-Root Path)
Since there's no root, don't try `wm` tricks or a rooted screenshot method —
objection's runtime patch is the correct tool here.

```bash
objection -g <package.name> explore
# inside objection:
android ui FLAG_SECURE false
```

- This flips the flag at runtime via Frida under the hood — no APK repatch
  needed if Gadget is already attached.
- Re-run `adb exec-out screencap -p` (or `agent-device screenshot`)
  immediately after — confirm the capture is no longer black before moving
  on.
- Log which screen had FLAG_SECURE set in `hook-notes.md`. A screen that
  actively hides itself from screenshots is a spidy-sense signal on its own —
  it usually means sensitive data (card numbers, OTP, seed phrases) renders
  there. Pivot into that screen's traffic once the bypass confirms.
- Other objection one-liners worth running early on any new target:
  ```bash
  android sslpinning disable          # before touching Caido — no pinning, no MITM
  android keystore list               # enumerate stored keys/certs
  android hooking list activities     # map attack surface
  android hooking list classes        # for later frida script targeting
  ```

## Frida — Runtime Hooking
Gadget model — attach, don't spawn:

```bash
frida -H 127.0.0.1:27042 Gadget -l ~/hunts/mobile-tools/apks/lab/hook.js
```

- `-H 127.0.0.1:27042` is the Gadget's exposed port (set via the Gadget
  config when the APK was patched) — confirm this matches the current
  session's patched build before assuming a hook failure is a script bug.
- Hook script targeting comes from `android hooking list classes` /
  `list class-methods` output in objection — build `hook.js` from confirmed
  class/method names, not guesses.
- **What to hook, feature-driven** (same philosophy as web — the feature
  determines the attack, not a checklist):
  - Crypto calls (`javax.crypto.Cipher`, custom crypto wrappers) — weak
    keys, hardcoded IVs, ECB mode.
  - Root/jailbreak/emulator detection methods — bypass to keep testing on
    the lab device.
  - Certificate pinning implementations objection's blanket bypass missed
    (custom `TrustManager`/`HostnameVerifier` classes — check
    `list classes` for anything not matching known pinning libs).
  - Local auth checks (biometric/PIN gate methods) — return true to skip if
    it's blocking further exploration.
  - Any method touching `SharedPreferences`, keystore, or local DB — log
    args/return values to spot plaintext secrets.
- Log every hook that fires with meaningful data to `hook-notes.md`
  immediately — this is the mobile equivalent of `interesting.md`, same
  discipline: log even if it looks like a dead end.

## APK Acquisition & Secret Sweep
Only if the target APK isn't already on the device:
- Grab it first from the Play Store developer page (the URL that shows all
  the target's apps — a catalogue worth mining); fall back to apkpure /
  apkmirror if a store download blocks or truncates. Verify the APK against
  the actual store listing (a mirror can host a stale/altered build).
- Run the jadx first-pass sweep on a fresh APK before any hooking:
  hardcoded secrets (API keys, AWS/Firebase URLs, JWTs), internal API
  endpoints, Firebase config, exported-component list from the manifest.
  A hardcoded JWT usable against the API is a writeup on its own, but the
  best hits are endpoints/secrets that unlock a server-side class (IDOR,
  ATO) against the web API.

## jadx MCP — Static Analysis
Use jadx MCP to read decompiled source rather than eyeballing raw smali:

- Pull the APK's class list and grep for interesting sink patterns before
  writing Frida hooks — confirms real method signatures instead of guessing
  from objection's runtime class list alone.
- Cross-reference: if Frida hooking shows a method firing with suspicious
  data, pull that method's decompiled source via jadx MCP to understand the
  full logic path (what calls it, what it does with the return value)
  before deciding if it's actually exploitable.
- Look for: hardcoded API keys/secrets, debug flags left in release builds,
  exported components (`Activity`/`Service`/`Receiver`/`Provider` with
  `exported="true"` in the manifest — pull `AndroidManifest.xml` via jadx
  MCP first, it's the fastest map of attack surface on a new APK).
- Deep-link handling code is a priority read — intent-based attacks
  (unvalidated deep link params, implicit intent hijacking) are a common
  class jadx surfaces fast that dynamic testing alone can miss.

## Caido MCP — Traffic Interception
Once SSL pinning is down (via objection above), route the device's traffic
through Caido same as any web target:

```bash
adb shell settings put global http_proxy <caido-host>:8081
```

If Caido runs on the same host machine as ADB (not a separate box on the
LAN), the device can't reach it via `127.0.0.1` — use the host's LAN IP, or
`adb reverse tcp:8081 tcp:8081` and point the device at `127.0.0.1:8081`
through the reverse tunnel instead.

- Install Caido's CA cert on the device (`adb push` the cert, then install
  via device settings, or objection's cert-pinning bypass path if pinning
  fights back after the proxy is set).
- From here, standard bug-hunting skill vulnerability classes apply to the
  mobile app's API traffic: IDOR, mass assignment, JWT attacks, auth
  bypass — same curl/Caido workflow as web, the client is just the app
  instead of a browser.
- Correlate: an interesting Frida hook (e.g. a local auth check) that also
  corresponds to an API call in Caido history is a strong lead — client-side
  gate + server-side trust in the client is a classic bypass chain.

## Vulnerability Classes — Mobile-Specific
- **Insecure local storage**: SharedPrefs, SQLite DBs, files in
  `/data/data/<package>/` — pull via objection (`android sms list` /
  browse commands) or hook read/write calls directly with Frida.
- **Exported component abuse**: launch exported activities directly via
  adb, bypassing intended app flow:
  ```bash
  adb shell am start -n <package>/<exported.activity>
  ```
- **Deep link / intent injection**: craft malicious intents targeting
  exported components found via jadx manifest read.
- **Weak crypto**: confirmed via Frida hooks on `Cipher`/`MessageDigest`
  calls — hardcoded keys, ECB, weak hashing for sensitive fields.
- **Client-side trust**: any check (root detection, jailbreak, local auth,
  license/subscription check) that's client-side only — confirm by hooking
  it, forcing a bypass, and checking whether the server ever validates the
  same thing independently.
- **WebView issues**: JS bridge exposure (`addJavascriptInterface`),
  `setJavaScriptEnabled` + loading untrusted URLs, file:// access — read
  WebView setup code via jadx MCP.

## Validation Requirement
Same discipline as web: before logging a finding as confirmed, capture raw
evidence — screenshot (post-FLAG_SECURE-bypass if relevant), Frida hook
output, and the corresponding Caido request ID. Don't log conclusions,
log evidence, and let @bug-validator (or manual re-check) confirm.
