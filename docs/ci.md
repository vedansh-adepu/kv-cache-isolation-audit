# CPU continuous integration

All three jobs run the entire correctness suite. A mutation passes only with
pytest exit 1, zero JUnit errors, at least one failure, and every failure message
in its family: always-miss requires "hit control"; broken-tenant requires
"isolation". Any unrelated failure, collection/setup/teardown error or unexpected
pass rejects the job. Intended kill counts appear in the job summary and result
JSON. Logs, JUnit and gate results upload as artifacts even on failure. Classifier
unit tests cover unrelated and mixed assertions, collection errors, empty results
and timeout diagnostics.

The Linux snapshot was resolved for CPython 3.12 on x86-64 glibc 2.39 from the
same pinned requirements as the macOS environment. The older glibc 2.28 target
cannot use llguidance 1.7.6's CPython-compatible wheel, which requires 2.31.
The workflow explicitly checks the runner architecture and glibc baseline.
The snapshot includes Linux's triton dependency and pins torch 2.13.0+cpu;
all distributions have hashes. Resolution does not demonstrate Linux execution.
The first reviewed workflow run must validate that environment on Ubuntu.

Upstream source is fetched by one exact commit, not installed as a compiled
vLLM package. No model is downloaded. CPU imports and real upstream cache
objects are the scope; GPU inference and timing remain outside this suite.
