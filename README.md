# KV cache isolation audit

This CPU correctness harness binds synthetic authenticated principals to tenant
cache namespaces at an in-process gateway. It uses the real vLLM Request,
block hashing and KVCacheManager from pinned v0.32.0 source. It checks
cross-tenant misses together with same-tenant hits, key lifecycle and replicas.
It loads no model and makes no timing or production authentication claim.

Developed with AI coding assistance; every change is reviewed by the author.

## Run

Use Python 3.12 and the tested CPU environment snapshot in requirements-cpu.txt
(torch 2.13.0, pytest 9.1.1). vLLM source must be a separate checkout at
5df63a7203cdb9328d824a27b682e77c7b9928be. No compiled vLLM extension is needed
for this tested path. Set VLLM_SOURCE to that checkout and CPU_PYTHON to the
existing environment's Python executable. From this repository:

```sh
PYTHONPATH="$VLLM_SOURCE:$PWD/src" VLLM_TARGET_DEVICE=cpu \
VLLM_NO_USAGE_STATS=1 DO_NOT_TRACK=1 HF_HUB_OFFLINE=1 \
TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$CPU_PYTHON" -B -m pytest tests -q
```

Run tests/test_pilot.py first for the three-path integration pilot. To run the
negative controls, repeat the suite with CACHE_AUDIT_MUTATION=always-miss or
CACHE_AUDIT_MUTATION=broken-tenant. Both commands must exit nonzero because
an intended correctness assertion fails. Mutation code is confined to tests.

The gateway has no runtime dependencies beyond Python's standard library.
uv.lock covers this package; requirements-cpu.txt is the complete tested
external import environment, not a portable vLLM distribution or GPU lock.
Use the supplied environment for tests; uv sync alone does not install vLLM.

See [policy](docs/adr/001-gateway-salt.md), [CPU results](docs/cpu-validation.md)
and [third-party attribution](NOTICE). Real authentication, engine network
access controls, external caches and GPU timing require separate validation.
