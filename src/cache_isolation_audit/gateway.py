"""Bind trusted post-authentication principals to deterministic cache salts."""
import base64
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import hashlib
import hmac
import re

class PolicyError(ValueError):
    """Reject a request before dispatch when policy inputs are unavailable."""

@dataclass(frozen=True)
class Principal:
    organization: str
    user: str

def canonical(*fields: str) -> bytes:
    """Encode UTF-8 fields with unsigned four-byte big-endian byte lengths."""
    result = bytearray()
    for value in fields:
        if not isinstance(value, str) or not value or len(value) > 256:
            raise PolicyError("missing or invalid policy field")
        try:
            encoded = value.encode("utf-8")
        except UnicodeError as error:
            raise PolicyError("invalid policy encoding") from error
        result.extend(len(encoded).to_bytes(4, "big"))
        result.extend(encoded)
    return bytes(result)

@dataclass(frozen=True)
class Gateway:
    key: bytes | None = field(repr=False)
    epoch: str | None = "e1"
    service: str = "cache-audit"
    environment: str = "test"
    scope: str = "organization"

    def salt(self, principal: Principal) -> str:
        if not isinstance(principal, Principal):
            raise PolicyError("trusted principal required")
        if not isinstance(self.key, bytes) or len(self.key) < 32:
            raise PolicyError("active key unavailable")
        if not isinstance(self.epoch, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", self.epoch):
            raise PolicyError("one valid active epoch required")
        if self.scope not in ("organization", "user"):
            raise PolicyError("unsupported tenant scope")
        # Validate both authoritative identifiers, even in organization scope.
        canonical(principal.organization, principal.user)
        fields = ["cache-isolation-v1", self.service, self.environment,
                  self.epoch, self.scope, principal.organization]
        if self.scope == "user":
            fields.append(principal.user)
        digest = hmac.new(self.key, canonical(*fields), hashlib.sha256).digest()
        return "g1." + self.epoch + "." + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def dispatch(self, principal: Principal, payload, send: Callable):
        """Copy permitted token input; ignore untrusted identity and salt fields."""
        salt = self.salt(principal)  # No dispatch or shared fallback on failure.
        items = payload.items() if isinstance(payload, Mapping) else payload
        body = {}
        try:
            for name, value in items:
                if not isinstance(name, str) or name in body:
                    raise PolicyError("duplicate or invalid request field")
                body[name] = value
        except (TypeError, ValueError) as error:
            raise PolicyError("invalid or ambiguous request") from error
        tokens = body.get("token_ids")
        if not isinstance(tokens, (list, tuple)) or not tokens or any(
            type(t) is not int or t < 0 for t in tokens
        ):
            raise PolicyError("nonempty integer token_ids required")
        return send({"token_ids": tuple(tokens), "cache_salt": salt})
