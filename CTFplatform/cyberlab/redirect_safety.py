"""
Reusable helper for validating "next" redirect targets.

This app takes a "next" value from a form field on several state-changing
routes (submit flag, use hint, reset lab, set mode) so it can send the
student back to the page they came from. Trusting that value blindly is
an open-redirect vulnerability -- and an ACCIDENTAL one, not one of the
5 intentional teaching labs, so it gets fixed rather than preserved.

Only same-site, relative paths are ever allowed. Anything with a scheme
(http://, https://, javascript:, etc.) or a network location (//evil.example,
which the browser treats as protocol-relative to evil.example) is rejected.
"""
from urllib.parse import urlparse


def safe_redirect_target(candidate, default="/"):
    """Return `candidate` if it's a safe, same-site relative path;
    otherwise return `default`.

    Safe means:
      - non-empty, starts with a single "/" (not "//" or "/\\", both of
        which browsers can treat as protocol-relative to another host)
      - has no scheme (no "http:", "https:", "javascript:", etc.)
      - has no netloc (no embedded host, e.g. "/\\evil.example" or
        "https://evil.example/x")

    Deliberately conservative: when in doubt, fall back to `default`
    rather than trying to cleverly allow more.
    """
    if not candidate or not isinstance(candidate, str):
        return default

    candidate = candidate.strip()

    # Reject backslashes outright -- some browsers normalize \ to / and
    # treat "/\evil.example" as protocol-relative.
    if "\\" in candidate:
        return default

    if not candidate.startswith("/"):
        return default

    # "//host/path" or "///host/path" are protocol-relative URLs, not
    # relative paths -- reject any path starting with more than one "/".
    if candidate.startswith("//"):
        return default

    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return default

    return candidate
