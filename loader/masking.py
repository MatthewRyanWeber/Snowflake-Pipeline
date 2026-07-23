"""PII masking applied on load. Pure functions — no I/O, fully unit-tested.

Policies are named in config/loader.yaml per column, so masking is data-driven and the
same rules are demonstrable whether or not the data is real (it isn't — Synthea).
"""

import hashlib

# Deterministic pseudonymization salt. Overridable via config; a real deployment would
# source this from a secret store, never commit a production salt.
DEFAULT_SALT = "snowflake-pipeline-synthetic"


def mask_ssn(value: str | None) -> str | None:
    """123-45-6789 -> XXX-XX-6789 (keep last 4 for referential debugging)."""
    if not value:
        return value
    digits = [c for c in value if c.isdigit()]
    if len(digits) < 4:
        return "XXX-XX-XXXX"
    return "XXX-XX-" + "".join(digits[-4:])


def mask_phone(value: str | None) -> str | None:
    """Keep last 4 digits: (212) 555-1234 -> (XXX) XXX-1234."""
    if not value:
        return value
    digits = [c for c in value if c.isdigit()]
    if len(digits) < 4:
        return "(XXX) XXX-XXXX"
    return "(XXX) XXX-" + "".join(digits[-4:])


def mask_email(value: str | None) -> str | None:
    """a.person@example.com -> a****@example.com."""
    if not value or "@" not in value:
        return value
    local, _, domain = value.partition("@")
    head = local[0] if local else ""
    return f"{head}****@{domain}"


def redact(value: str | None) -> str | None:
    """Full redaction — value never lands in RAW."""
    return None if value is None else "***REDACTED***"


def hash_sha256(value: str | None, salt: str = DEFAULT_SALT) -> str | None:
    """Deterministic pseudonym: same input -> same token, joinable but non-reversible."""
    if value is None:
        return None
    return hashlib.sha256((salt + str(value)).encode("utf-8")).hexdigest()


_POLICIES = {
    "ssn": mask_ssn,
    "phone": mask_phone,
    "email": mask_email,
    "redact": redact,
    "hash": hash_sha256,
}


def apply_policy(value, policy: str, salt: str = DEFAULT_SALT):
    """Dispatch a named policy. Unknown policy is a hard error (fail loud, don't pass raw PII)."""
    if policy == "hash":
        return hash_sha256(value, salt)
    try:
        fn = _POLICIES[policy]
    except KeyError as exc:
        raise ValueError(f"unknown masking policy: {policy!r}") from exc
    return fn(value)


def mask_row(row: dict, column_policies: dict, salt: str = DEFAULT_SALT) -> dict:
    """Return a new row with each configured column masked by its policy."""
    if not column_policies:
        return dict(row)
    out = dict(row)
    for col, policy in column_policies.items():
        if col in out:
            out[col] = apply_policy(out[col], policy, salt)
    return out
