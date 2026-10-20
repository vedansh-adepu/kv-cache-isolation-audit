# Bind cache namespaces to trusted gateway principals

The gateway receives an immutable principal after authentication and
authorization. Organization scope is the default; user scope includes both
organization and user IDs. Body fields cannot select either identity.
Client-supplied salts are removed; ambiguous duplicate fields are rejected.

Derive HMAC-SHA-256 over UTF-8 fields, each preceded by its unsigned four-byte
big-endian byte length: domain cache-isolation-v1, service, environment, epoch,
scope, organization ID, then user ID only for user scope. No delimiter-based
concatenation or prompt-token modification is used. Encode the full digest
as base64url without padding, prefixed with g1.<epoch>.; epoch has at most
16 validator-safe characters. Keys have at least 32 bytes and never enter
request data or logs. Public fixture keys are synthetic test material only.

A missing/invalid key, epoch or trusted principal rejects before dispatch.
There is no shared namespace fallback. Replicas with identical configuration
must derive identical namespaces. Operators coordinate epoch changes: new
requests use only the new key/epoch, never retry old namespaces on a miss.
Old in-flight work can finish; old cached blocks expire normally. Distribution,
authentication and secret-manager lifecycle are deployment responsibilities,
not implemented network services in this in-process harness.

Only the normal gateway path is a policy candidate. The test-only unsalted
baseline and propagation/cache-disabled mutations intentionally break it.
Logical correctness does not imply timing isolation, protection inside the
same organization, or isolation of external/semantic/multimodal caches.
