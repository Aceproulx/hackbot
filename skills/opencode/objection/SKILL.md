---
name: objection
description: Use when running Objection for Android app pentesting with Frida. Covers connect, hooking, SSL pinning bypass, FLAG_SECURE bypass, memory/sqlite/keystore operations, and custom Frida scripts via the patched Aceproulx/objection fork. Tested Android 14, Frida gadget 17.16.2.
---

# Objection — HackTricks Command Reference (Aceproulx fork)

Fork: https://github.com/Aceproulx/objection
Upstream: https://github.com/sensepost/objection
Reference: https://hacktricks.wiki/en/mobile-pentesting/android-app-pentesting/frida-tutorial/objection-tutorial/

`console.log()` works inside the objection REPL — no need for `send()`.

## Connect

```bash
# Attach by process name (recommended)
objection -n asvid.github.io.fridaapp start

# Via gadget (non-rooted device)
objection patchapk -s app-release.apk --network-security-config --enable-debug
adb install -r app-release.objection.apk
objection -n Gadget start
```

## Environment & Info

```
env
frida
ping
```

## File Operations

```
file download <remote path> [<local path>]
file upload <local path> [<remote path>]
```

## Loading Custom Frida Scripts

Scripts can use `console.log()` — output shown in both objection REPL and Frida CLI.
JADX "Copy as Frida script" works as-is (includes `Java.perform()` already).

| Method | Auto-wrap `Java.perform()`? | Syntax |
|--------|---------------------------|--------|
| objection `evaluate` | Yes | `evaluate script.js` |
| objection `--startup-script` | Yes | `objection -n pkg start --startup-script script.js` |
| Frida CLI `-l` | No (must wrap) | `frida -U -n pkg -l script.js` |

```bash
# Via objection REPL
evaluate hook.js

# Via startup script
objection -n asvid.github.io.fridaapp start --startup-script hook.js

# Via Frida CLI (USB)
frida -U -p $(adb pidof <package>) -l hook.js

# Via Frida CLI (Gadget)
adb forward tcp:27042 tcp:27042
frida -H 127.0.0.1:27042 Gadget -l hook.js
```

## Jobs

```
import ssl-bypass.js "ssl-bypass"
jobs list
jobs kill <job_id>
```

## SSL Pinning & Root Detection

```
android sslpinning disable
android root disable
android root simulate
android shell_exec whoami
```

## Screenshots & UI

```
android ui screenshot /tmp/screenshot
android ui FLAG_SECURE false
```

## Proxy & Deoptimize

```
android proxy set 192.168.1.10 8081
android deoptimize
android intent implicit_intents --dump-backtrace
```

## Static Analysis (Dynamic)

```
android hooking list activities
android hooking list services
android hooking list receivers
android hooking get current_activity
```

## Search Classes & Methods

```
android hooking search classes asvid.github.io.fridaapp
android hooking search methods asvid.github.io.fridaapp MainActivity
android hooking list class_methods asvid.github.io.fridaapp.MainActivity
android hooking list classes
android hooking list class_loaders
```

## Hooking

```
# Hook single method with all options
android hooking watch class_method asvid.github.io.fridaapp.MainActivity.sum --dump-args --dump-backtrace --dump-return

# Hook entire class
android hooking watch class asvid.github.io.fridaapp.MainActivity --dump-args --dump-return

# Change boolean return value
android hooking set return_value asvid.github.io.fridaapp.MainActivity.checkPin true
```

## Heap / Class Instances

```
android heap search instances <class>
android heap print fields <hashcode>
android heap print methods <hashcode> --without-arguments
android heap execute <hashcode> <method> --return-string
android heap evaluate <hashcode>
```

## Keystore & Intents

```
android keystore list
android intent launch_activity
android intent launch_service
```

## Memory

```
memory dump all <local destination>
memory dump from_base <base_address> <size> <local destination>
memory list modules
memory list exports libfoo.so
memory list exports libfoo.so --json exports.json
memory search "<pattern eg: 41 41 41 ?? 41>" (--string) (--offsets-only)
memory write "<address>" "<pattern eg: 41 41 41 41>" (--string)
```

## SQLite

```
sqlite connect /data/data/<package>/databases/app.db
sqlite connect /data/data/<package>/databases/app.db --sync
```

## Early Instrumentation

```
objection -n asvid.github.io.fridaapp start --startup-command "android sslpinning disable"
```

## Patches in Aceproulx Fork

- `console.log()` output displays in objection REPL (Frida `type: "log"` handled)
- `evaluate` and `--startup-script` auto-wrap in `Java.perform()` — bare `Java.use()` works
- Indirect eval `(0, eval)(...)` fixes V8 strict mode variable scoping
- Agent JS loads with `(frida.TransportError, frida.InvalidArgumentError)` fallback for large scripts
- `normalizePattern()` converts dot syntax (`Class.method`) to `!` syntax
- `class`/`class_method` search prefixes skipped in hooking commands
- Class name mangling in `watch` fixed for multi-dot names
