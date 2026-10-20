# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the vLLM project
"""Real upstream objects; fixture constructors adapted from vLLM Apache-2.0 tests."""
import os
from pathlib import Path
import subprocess
import pytest
import torch
from vllm import SamplingParams
from vllm.utils.hashing import sha256
from vllm.v1.core.kv_cache_manager import KVCacheManager
from vllm.v1.core.kv_cache_utils import get_request_block_hasher, init_none_hash
from vllm.v1.kv_cache_interface import FullAttentionSpec, KVCacheConfig, KVCacheGroupSpec
from vllm.v1.request import Request
from cache_isolation_audit.gateway import Gateway, Principal

PIN = "5df63a7203cdb9328d824a27b682e77c7b9928be"
KEY = bytes(range(32))  # Public synthetic test material only.
A = Principal("org-a", "user-a")
B = Principal("org-b", "user-b")
TOKENS = list(range(48)) + [99] * 11

@pytest.fixture(autouse=True, scope="session")
def pinned_source():
    root = Path(os.environ["VLLM_SOURCE"]).resolve()
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == PIN
    assert subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=root).returncode == 0
    for cls in (Request, KVCacheManager, get_request_block_hasher, init_none_hash, sha256):
        import inspect
        assert Path(inspect.getfile(cls)).resolve().is_relative_to(root)
    init_none_hash(sha256)

class Engine:
    def __init__(self, gateway=None, caching=True, unsalted=False):
        self.gateway = gateway or Gateway(KEY)
        self.dispatches = 0
        self.unsalted = unsalted
        self.mutation = os.environ.get("CACHE_AUDIT_MUTATION", "none")
        assert self.mutation in ("none", "always-miss", "broken-tenant")
        config = KVCacheConfig(num_blocks=32, kv_cache_tensors=[], kv_cache_groups=[
            KVCacheGroupSpec(["layer"], FullAttentionSpec(
                block_size=16, num_kv_heads=1, head_size=1, dtype=torch.float32))])
        self.manager = KVCacheManager(config, max_model_len=8192,
                                      scheduler_block_size=16, hash_block_size=16,
                                      enable_caching=caching and self.mutation != "always-miss")

    def request(self, principal=A, tokens=None, gateway=None, **untrusted):
        def send(normalized):
            self.dispatches += 1
            params = SamplingParams(max_tokens=17)
            params.update_from_generation_config({}, eos_token_id=100)
            salt = normalized["cache_salt"]
            if self.mutation == "broken-tenant":
                salt = "shared-test-namespace"  # Deliberate test-only propagation fault.
            if self.unsalted:
                salt = None  # Real upstream unsalted baseline, never gateway policy.
            return Request(str(self.dispatches), list(normalized["token_ids"]), params,
                           None, cache_salt=salt,
                           block_hasher=get_request_block_hasher(16, sha256))
        return (gateway or self.gateway).dispatch(
            principal, {"token_ids": TOKENS if tokens is None else tokens, **untrusted}, send)

    def lookup(self, request):
        blocks, count, _ = self.manager.get_computed_blocks(request)
        assert count == len(blocks.blocks[0]) * 16
        return count

    def prime(self, principal=A, tokens=None, gateway=None):
        request = self.request(principal, tokens, gateway)
        blocks, count, _ = self.manager.get_computed_blocks(request)
        assert count == 0
        allocation = self.manager.allocate_slots(request, request.num_tokens, count, blocks)
        assert allocation is not None
        request.num_computed_tokens = request.num_tokens
        return request

@pytest.fixture
def engine():
    return Engine()
