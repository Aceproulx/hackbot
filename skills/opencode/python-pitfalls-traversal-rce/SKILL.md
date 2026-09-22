---
name: python-pitfalls-traversal-rce
description: >
  Use this skill during authorized bug bounty / pentest recon or code review whenever a target is (or may be) built in Python and handles user-controlled input in file paths, URLs, serialized objects, YAML, or merged/nested dictionaries. Covers six Python function/library "pitfalls" that look safe but aren't: os.path.join and pathlib.joinpath silently discarding earlier path segments when a later segment is absolute (path traversal / arbitrary file read/write), pickle.loads on untrusted input (deserialization RCE via __reduce__), PyYAML's yaml.load with the default/unsafe Loader (deserialization RCE via python/object tags), urllib.parse.urljoin discarding the entire base URL when given an absolute URL as a later argument (SSRF / open redirect / allowlist bypass), and Python "class pollution" via insecure recursive dict-merge-into-object functions using setattr/getattr (arbitrary attribute overwrite, potentially RCE via gadget chains). Trigger on requests to review Python source for these functions, blackbox-test a Python/Flask/Django backend for path traversal or SSRF, or "find Python-specific bugs".
metadata:
  source: https://www.yeswehack.com/learn-bug-bounty/python-pitfalls-turning-developer-mistakes
---

# Python Pitfalls: Path Traversal, Deserialization RCE, Class Pollution

From Alex Brumen ("Brumens"), YesWeHack researcher enablement. Six specific standard-library/common-library behaviors that developers routinely assume are "safe by default" and aren't. Useful for both whitebox grep-for-patterns review and blackbox black-box fingerprinting.

## General blackbox approach

Before diving into specific functions, fingerprint whether input triggers Python-specific logic by watching for: time delays, content differences, error messages, reflected values, differing process results, verbose stack traces, and syntax-sensitive parsing differences between a benign and a weaponized payload. A behavior that appears only with a crafted payload (not a benign one) signals input-dependent code logic worth digging into further. In general, be suspicious of any function that (a) changes behavior based on input structure, (b) normalizes/reformats input rather than treating it as opaque data, or (c) parses/interprets input instead of storing it raw.

## 1. `os.path.join` — path traversal via absolute-path truncation

`os.path.join("/user/uploads/", user_input)` **discards everything before an absolute path** if `user_input` starts with `/`. Developers routinely assume this function sanitizes/contains paths — it does not.
```python
os.path.join("/user/uploads/", "/etc/passwd")  # → "/etc/passwd", NOT "/user/uploads//etc/passwd"
```
**Test:** anywhere user input feeds a later argument to `os.path.join`, try an absolute path (`/etc/passwd`, `/proc/self/environ`, a target upload path) as the payload. Real CVEs from this exact pattern: CVE-2025-57403 (Gerapy, path traversal → RCE via arbitrary file write), CVE-2025-6278 (Upsonic, absolute-path truncation → arbitrary file read), and a Setuptools `PackageIndex.download` issue (malicious archive contents escaping the extraction directory).

## 2. `pathlib.joinpath` — same pitfall, different API

`Path(base).joinpath("files", user_input)` behaves identically to `os.path.join` for this purpose: an absolute-path segment discards everything before it, and `..` segments are not blocked either.
```python
Path("/var/www/html").joinpath("files", "/etc/passwd")  # → Path("/etc/passwd")
```
Test the same way as `os.path.join`.

## 3. `pickle.loads` — deserialization RCE

Never expect `pickle.loads` to be safe on untrusted input — it's not a pitfall so much as an outright vulnerability class (CWE-502). Any object implementing `__reduce__` can specify a callable + args that fire during unpickling:
```python
class RCE:
    def __reduce__(self):
        return (os.system, ("id",))
pickled = pickle.dumps(RCE())
```
**Test:** find any place `pickle.loads`/`pickle.load` is called on data that ultimately comes from a request (a cookie, a cache value, a session store, a message queue payload, a file upload). A base64/hex-encoded blob in an otherwise-innocuous-looking parameter (session tokens, cache keys) is a strong signal — try decoding and pickle-disassembling it (`pickletools.dis`) before assuming it's opaque. Real CVEs: CVE-2025-3108 (JsonPickleSerializer defaulting to `pickle.loads`), CVE-2026-23946 (Helpdesk module, requires staff auth), CVE-2025-1716 (malicious pickle bypassing Picklescan static analysis — don't trust a scanner's "safe" verdict alone).

## 4. `PyYAML` `yaml.load()` without a safe loader — deserialization RCE

Same underlying class of bug as pickle, reached via YAML instead. If a safe loader isn't explicitly passed (`yaml.load(data, Loader=yaml.Loader)` instead of `yaml.safe_load(data)` or `Loader=yaml.SafeLoader`), YAML's `!!python/object/apply:` tag can instantiate arbitrary Python objects/call arbitrary functions during parse:
```yaml
!!python/object/apply:os.system ["id"]
```
**Test:** any endpoint/config-import feature that accepts YAML (CI config, app config upload, data import) — try a `!!python/object/apply:` payload targeting a low-impact function first (`print`) to confirm the sink before escalating. Real CVEs: CVE-2025-50460 (ms-swift test runner), CVE-2026-24009 (Docling Core's `load_from_yaml`, PyYAML < 5.4).

## 5. Python "class pollution" — insecure recursive object merge

Not tied to one function — this is a pattern found in hand-rolled "deep merge a dict into an object" utilities (common in config-loading, form-binding, or API-patch-style code) that recurse using `setattr`/`getattr`/`hasattr` without restricting which attribute names are settable:
```python
def merge(source, destination):
    for key, value in source.items():
        if hasattr(destination, "get"):
            ...
        elif hasattr(destination, key) and type(value) == dict:
            merge(value, getattr(destination, key))
        else:
            setattr(destination, key, value)
```
A payload targeting dunder-chained attributes can walk into interpreter internals:
```python
payload = {"__init__": {"__globals__": {"some_var": "polluted"}}}
merge(payload, some_object)  # overwrites a module-level global via the object's __init__'s __globals__
```
**Test:** find any endpoint that accepts a nested JSON body and merges it "onto" an existing object/model (common in PATCH-style update endpoints, config-override features, or object-hydration from request bodies). Try dunder-key payloads (`__init__`, `__class__`, `__globals__`, `__builtins__`) in nested positions and watch for unexpected side effects elsewhere in the app (CWE-454 external init of trusted data, CWE-269 improper privilege management, CWE-94 code injection). Real CVE: CVE-2025-58367 (DeepDiff's `Delta` class constructor — a class-pollution gadget flips `deepdiff.serialization.SAFE_TO_IMPORT` to permit dangerous classes like `posix.system`, enabling insecure pickle deserialization downstream).

## 6. `urllib.parse.urljoin` — base-URL discard, unlike the path-join pitfalls

Different failure mode from #1/#2: instead of truncating, `urljoin` **discards the entire base URL** if given an absolute URL as the second argument:
```python
urljoin("http://example.com/", "http://evil.com/")  # → "http://evil.com/"
```
This is exploitable wherever an app builds a "safe" URL by joining a trusted base with user-supplied input, assuming the base always survives.
**Test:** any redirect-building, internal-request-building (SSRF-prone), or "allowlisted base URL + user path" logic that uses `urljoin`. Try supplying a full absolute URL (`http://attacker.example/`) or a scheme-relative URL (`//attacker.example/`) as the user-controlled component and see whether the resulting request/redirect goes to your host instead of staying under the intended base. Real-world variant: CVE-2024-42353 (WebOb) — a `Location` header starting with `//` was parsed by `urlparse` as a scheme-less URI, with the following segment misread as a hostname, which `urljoin` then substituted for the real one. CVE-2025-68696 (httparty) — SSRF risking API-key leakage and internal-server access. Relevant CWEs: CWE-918 (SSRF), CWE-22 (path traversal, if the "URL" ends up used as a path), CWE-601 (open redirect).

## Reporting checklist

- The exact sink (file path used in `os.path.join`/`joinpath`, `pickle.loads`/`yaml.load` call site, merge function, `urljoin` call) and how user input reaches it.
- A minimal payload and observed impact (file content read, command executed, attribute overwritten, request redirected off-host).
- Cite the matching CVE class above if relevant — it helps triagers quickly grasp severity and precedent.
- Recommend the safe alternative explicitly: reject/normalize absolute paths and `..` before joining (or use `os.path.commonpath`/containment checks after resolving), never `pickle.loads` untrusted data, always `yaml.safe_load`, avoid `setattr`/`getattr` on attacker-controlled key names (allowlist fields), and validate `urljoin` output stays within the intended origin before using it.
