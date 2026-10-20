"""Paired tenant/utility checks against actual pinned upstream cache objects."""
from dataclasses import replace
import hashlib
import hmac
import re
import sys
import pytest
from vllm.entrypoints.generate.base.protocol import validate_cache_salt
from cache_isolation_audit.gateway import Gateway, PolicyError, Principal, canonical
from conftest import A, B, Engine, KEY, TOKENS

def hit(engine, principal=A, **kwargs):
    assert engine.lookup(engine.request(principal, **kwargs)) == 48, "same-tenant hit control"

def miss(engine, principal=B, **kwargs):
    assert engine.lookup(engine.request(principal, **kwargs)) == 0, "cross-tenant isolation"

def test_client_salt_stripped(engine):
    engine.prime()
    for value in [None, "chosen", engine.gateway.salt(B), {"hostile": True}]:
        req = engine.request(cache_salt=value)
        assert req.cache_salt == engine.gateway.salt(A)
        assert engine.lookup(req) == 48, "same-tenant hit control"
    miss(engine)

def test_missing_salt_injected(engine):
    request = engine.request()
    assert request.cache_salt and request.cache_salt == engine.gateway.salt(A)
    engine.prime()
    hit(engine)
    miss(engine)

def test_cross_tenant_and_unsalted_control(engine):
    engine.prime()
    hit(engine)
    miss(engine)
    hit(engine)
    # A shared namespace demonstrates that real lookup can reuse across clients.
    shared = Engine(unsalted=True)
    shared.prime()
    assert shared.lookup(shared.request(B)) == 48, "unsalted cross-tenant hit control"

def test_same_tenant_and_disabled_cache(engine):
    engine.prime()
    hit(engine)
    disabled = Engine(caching=False)
    disabled.prime()
    assert disabled.lookup(disabled.request()) == 0
    hit(engine)

def test_forged_salt_cannot_impersonate_tenant(engine):
    engine.prime()
    miss(engine, cache_salt=engine.gateway.salt(A), organization="org-a", user="user-a", epoch="e1")
    hit(engine)
    engine.prime(B)
    hit(engine, B)
    hit(engine)

def test_replica_consistency(engine):
    replica = Gateway(bytes(KEY), epoch="e1")
    assert replica is not engine.gateway and replica.salt(A) == engine.gateway.salt(A)
    engine.prime()
    hit(engine, gateway=replica)
    miss(engine, gateway=replica)
    hit(engine)

def test_rotation_cold_then_warm_and_no_fallback(engine):
    engine.prime()
    hit(engine)
    rotated = Gateway(bytes(reversed(KEY)), epoch="e2")
    replica = replace(rotated)
    assert replica.salt(A) == rotated.salt(A) != engine.gateway.salt(A)
    assert engine.lookup(engine.request(gateway=rotated, cache_salt=engine.gateway.salt(A), epoch="e1")) == 0
    hit(engine)  # Existing old-epoch request path remains isolated and usable.
    engine.prime(gateway=rotated)
    hit(engine, gateway=replica)
    miss(engine, gateway=rotated)
    miss(engine)
    hit(engine)
    hit(engine, gateway=rotated)

@pytest.mark.parametrize("bad", [Gateway(None), Gateway(b"short"), Gateway(KEY, epoch=None), Gateway(KEY, epoch=""), Gateway(KEY, epoch="e1,e2")])
def test_missing_key_or_epoch_never_dispatches(engine, bad):
    engine.prime()
    count = engine.dispatches
    with pytest.raises(PolicyError):
        engine.request(gateway=bad, cache_salt="client-fallback")
    assert engine.dispatches == count
    hit(engine)

@pytest.mark.parametrize("principal", [None, {}, Principal("", "user"), Principal("org", "")])
def test_missing_trusted_principal_fails_closed(engine, principal):
    engine.prime()
    count = engine.dispatches
    with pytest.raises(PolicyError):
        engine.request(principal)
    assert engine.dispatches == count
    hit(engine)

def test_organization_and_user_scopes(engine):
    peer = Principal(A.organization, "different-user")
    engine.prime()
    hit(engine, peer)  # Organization sharing is intentional.
    user_gateway = replace(engine.gateway, scope="user")
    separate = Engine(user_gateway)
    separate.prime()
    hit(separate)
    miss(separate, peer)
    hit(separate)

@pytest.mark.parametrize("length,expected", [(48, 32), (59, 48), (64, 48)])
def test_block_boundary_and_partial_tail(engine, length, expected):
    tokens = list(range(length))
    engine.prime(tokens=tokens)
    assert engine.lookup(engine.request(tokens=tokens)) == expected, "same-tenant hit control"
    assert engine.lookup(engine.request(B, tokens=tokens)) == 0, "cross-tenant isolation"
    assert engine.lookup(engine.request(tokens=tokens)) == expected, "same-tenant hit control"

def test_divergent_suffix_reuses_only_prefix(engine):
    engine.prime()
    probe = TOKENS[:32] + [77] * 27
    assert engine.lookup(engine.request(tokens=probe)) == 32, "same-tenant prefix hit control"
    miss(engine, tokens=probe)
    hit(engine)

def test_canonical_and_hmac_vector_and_domains():
    assert canonical("ab", "c").hex() == "0000000261620000000163"
    assert canonical("ab", "c") != canonical("a", "bc")
    # RFC 4231 case 1, independent of the gateway's namespace encoding.
    assert hmac.new(bytes.fromhex("0b" * 20), b"Hi There", hashlib.sha256).hexdigest() == "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"
    gateway = Gateway(KEY)
    salt = gateway.salt(A)
    assert re.fullmatch(r"g1\.e1\.[A-Za-z0-9_-]{43}", salt)
    validate_cache_salt(salt)
    assert len({salt, replace(gateway, service="other").salt(A), replace(gateway, environment="other").salt(A), replace(gateway, scope="user").salt(A), replace(gateway, epoch="e2").salt(A), gateway.salt(B)}) == 6
    assert "vllm._C" not in sys.modules

@pytest.mark.parametrize("payload", [[("token_ids", [1]), ("cache_salt", "a"), ("cache_salt", "b")], {"token_ids": []}, {"token_ids": [True]}, {"token_ids": [-1]}])
def test_malformed_input_rejects_before_send(engine, payload):
    engine.prime()
    called = []
    with pytest.raises(PolicyError):
        engine.gateway.dispatch(A, payload, called.append)
    assert called == []
    hit(engine)
