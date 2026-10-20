"""Three-path pilot runs before expanding the contract case matrix."""
import pytest
from cache_isolation_audit.gateway import Gateway, PolicyError
from conftest import A, B, KEY

def test_pilot_normalize_prime_repeat(engine):
    engine.prime()
    request = engine.request(cache_salt="untrusted")
    assert request.cache_salt == engine.gateway.salt(A)
    assert engine.lookup(request) == 48, "same-tenant hit control"

def test_pilot_forged_salt_and_control(engine):
    engine.prime()
    assert engine.lookup(engine.request()) == 48, "same-tenant hit control"
    forged = engine.request(B, cache_salt=engine.gateway.salt(A), organization="org-a", user="user-a")
    assert engine.lookup(forged) == 0, "cross-tenant isolation"
    assert engine.lookup(engine.request()) == 48, "same-tenant hit control"

def test_pilot_missing_key_and_restoration(engine):
    engine.prime()
    count = engine.dispatches
    with pytest.raises(PolicyError):
        engine.request(gateway=Gateway(None), cache_salt="fallback-attempt")
    assert engine.dispatches == count
    assert engine.lookup(engine.request(gateway=Gateway(KEY))) == 48, "same-tenant hit control"
