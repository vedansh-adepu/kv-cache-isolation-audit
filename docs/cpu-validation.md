# CPU correctness results

These results use the real pinned vLLM Request, SHA-256 block hashing and
KVCacheManager metadata path, not model execution or substitute lookup code.
Date: 19 October 2026. Hardware: Apple M2, 8 cores, 8 GB RAM, macOS arm64 CPU.
Python 3.12.15, torch 2.13.0 from the CPU index, pytest 9.1.1. The Darwin torch
wheel includes MPS support; this test does not invoke it. vLLM commit:
5df63a7203cdb9328d824a27b682e77c7b9928be. The test guard verifies the clean
tracked source and imported Request, hash helpers and manager paths.

| Run | Observation | Meaning |
|---|---|---|
| Three-path pilot | 3 passed | Normalize/prime/repeat, forged-salt miss with hit control, missing-key rejection and restoration |
| Complete suite | 29 passed | Eight policy case/control pairs, user/organization scope, alignment and malformed inputs |
| always-miss | 28 failed, 1 passed; exit 1 | Real cache disabled: utility control sees 0 instead of 48 tokens |
| broken-tenant | 13 failed, 16 passed; exit 1 | Test adapter drops tenant propagation: isolation control sees 48 instead of 0 tokens |

Both mutations are intentionally failing test modes confined to fixtures.
Neither mode replaces hashing or lookup. The unsalted baseline intentionally
passes salt=None to real Requests and demonstrates cross-tenant reuse.
Normal policy does not dispatch unsalted requests. Synthetic keys and principals
are public fixtures; no real credential or private request is used.

All runs retain 15 upstream warnings: one missing generated vLLM version module
and 14 TorchScript deprecations. The explicit source hash guard pins the version
despite that metadata warning. Maximum captured child-process RSS across the
test attempts: 447627264 bytes. This is process
memory, not a GPU memory measurement or a system-wide peak.

Exact receipt summaries, source hashes and environment-snapshot hash are in
[cpu-results.json](cpu-results.json). Reproduce with the [README command](../README.md)
and repeat it with each mutation environment variable. Run the pilot first.
requirements-cpu.txt records the tested external environment; uv.lock covers
only this stdlib policy package. No weights or compiled vLLM extension is used.

The principal is a post-authentication fixture, not a verified external HTTP
session. These results show the declared in-process correctness boundary.
They do not establish deployed authentication, secret-manager coordination,
engine network access control, production eviction behavior or timing privacy.
