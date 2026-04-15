"""Input sanitization for AppleScript and other shell contexts."""

import re


def escape_applescript(s: str) -> str:
    """Escape a string for safe embedding in AppleScript double-quoted strings.

    Handles: backslashes, double quotes, and other control characters
    that could break out of an AppleScript string literal.
    """
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    return s


def sanitize_app_name(name: str) -> str | None:
    """Validate and sanitize an application name.

    Returns the cleaned name, or None if it looks malicious.
    App names should be alphanumeric with spaces, hyphens, dots, and parens.
    """
    # Strip whitespace
    name = name.strip()
    if not name:
        return None
    # App names should not contain AppleScript control characters or shell metacharacters
    if re.search(r'[;|&`$\n\r]', name):
        return None
    # Reasonable length limit
    if len(name) > 100:
        return None
    return escape_applescript(name)


def sanitize_url(url: str) -> str | None:
    """Validate and sanitize a URL for embedding in AppleScript.

    Returns escaped URL or None if suspicious.
    """
    url = url.strip()
    if not url:
        return None
    # Must start with http/https or be a bare domain
    if not re.match(r'^https?://', url):
        url = f"https://{url}"
    # No AppleScript injection via URL
    if re.search(r'["\n\r]', url):
        return None
    if len(url) > 2000:
        return None
    return escape_applescript(url)
