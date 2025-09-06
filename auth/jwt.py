"""
JWT (HS256) implementation using Python standard library only.
Base64url without padding, HMAC-SHA256 signature, exp validation.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict


def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """Base64url decode with automatic padding restoration."""
    s = data.encode("ascii")
    padding = b"=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def now_ts() -> int:
    """Return current UNIX timestamp (seconds)."""
    return int(time.time())


def encode(payload: Dict[str, Any], secret: str) -> str:
    """
    Encode a JWT token with HS256.
    Requires payload to contain 'exp' (int UNIX timestamp). Optionally include 'iat'.
    """
    try:
        if "exp" not in payload:
            raise ValueError("JWT payload missing 'exp'")
        # Basic validation
        exp = payload["exp"]
        if not isinstance(exp, int):
            raise ValueError("'exp' must be an integer UNIX timestamp")

        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        sig_b64 = _b64url_encode(signature)
        return f"{header_b64}.{payload_b64}.{sig_b64}"
    except Exception as e:
        # Normalize all errors to ValueError for caller simplicity
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"JWT encode failed: {e}")


def decode(token: str, secret: str) -> Dict[str, Any]:
    """
    Decode and verify a JWT token with HS256.
    - Verifies signature
    - Validates 'exp' is present and not expired
    Returns the payload (claims) on success.
    Raises ValueError on any failure.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        header_b64, payload_b64, sig_b64 = parts
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise ValueError("Unsupported JWT header")

        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise ValueError("Invalid JWT signature")

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        exp = payload.get("exp")
        if not isinstance(exp, int):
            raise ValueError("Invalid 'exp' in payload")
        if now_ts() >= exp:
            raise ValueError("Token expired")

        return payload
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"JWT decode failed: {e}")