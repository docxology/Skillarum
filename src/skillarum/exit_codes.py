"""Stable exit-code contract for the Skillarum CLI.

Every command must exit with one of these codes:

===== ===================================================================
Code  Meaning
===== ===================================================================
0     Success (including reports that completed with advisory warnings,
      e.g. ``drift``/``verify``/``doctor``/``research`` ok verdicts).
1     Validation or verification failure: a skill failed structural
      validation, a ledger check failed, a requested input file is
      missing/invalid, or a diagnostic report says ``ok: false``.
2     Usage or configuration error: the command line itself was wrong
      (argparse rejects unknown flags/missing arguments with this code).
3     Environment or network failure: an HTTP request to a configured
      endpoint (Ollama, profile base URL) failed for environmental
      reasons rather than because of the provided inputs.
===== ===================================================================

The codes are part of the public contract; scripts may branch on them.
Do not return ad-hoc codes from command handlers.
"""

from __future__ import annotations

EXIT_OK = 0
"""Command succeeded."""

EXIT_FAILURE = 1
"""Validation/verification failure or an invalid/missing input artifact."""

EXIT_USAGE = 2
"""Usage or configuration error (argparse-level command-line rejection)."""

EXIT_ENVIRONMENT = 3
"""Environment or network failure (endpoint unreachable, HTTP error)."""

__all__ = [
    "EXIT_OK",
    "EXIT_FAILURE",
    "EXIT_USAGE",
    "EXIT_ENVIRONMENT",
]
