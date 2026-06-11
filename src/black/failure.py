"""Structured failure classification for Black formatting errors.

Provides stable, machine-readable error codes and human-readable summaries
that can be reused by both the CLI and the blackd HTTP server.
"""

import re
from dataclasses import dataclass
from enum import IntEnum

from black.parsing import ASTSafetyError, InvalidInput, SourceASTParseError

# Code ranges: 1xx = parsing/formatting, 2xx = notebook, 3xx = protocol, 9xx = unknown


class FailureCode(IntEnum):
    """Stable error codes for Black formatting failures.

    Numeric values are part of the public API and must not change.
    """

    SYNTAX_ERROR = 100
    AST_EQUIVALENCE = 101
    AST_PARSE_FAILURE = 102
    FORMAT_INSTABILITY = 103
    INVALID_NOTEBOOK = 200
    INVALID_HEADER = 300
    INVALID_VARIANT = 301
    UNKNOWN = 900


_SUMMARIES: dict[FailureCode, str] = {
    FailureCode.SYNTAX_ERROR: "Source code contains a syntax error",
    FailureCode.AST_EQUIVALENCE: (
        "Formatted output is not AST-equivalent to source (Black bug)"
    ),
    FailureCode.AST_PARSE_FAILURE: (
        "Source cannot be parsed by ast.parse(); "
        "consider --target-version or --fast"
    ),
    FailureCode.FORMAT_INSTABILITY: (
        "Formatted code is not stable across passes (Black bug)"
    ),
    FailureCode.INVALID_NOTEBOOK: "File is not a valid Jupyter notebook",
    FailureCode.INVALID_HEADER: "Invalid request header",
    FailureCode.INVALID_VARIANT: "Invalid Python variant header",
    FailureCode.UNKNOWN: "An unexpected error occurred",
}


@dataclass(frozen=True)
class Failure:
    """A classified formatting failure.

    Attributes:
        code: Stable machine-readable error code.
        summary: One-line human-readable explanation.
        detail: Sanitized detail from the original exception (no paths/traces).
    """

    code: FailureCode
    summary: str
    detail: str


# ---------------------------------------------------------------------------
# Privacy: scrub absolute paths and temp-file references from messages
# ---------------------------------------------------------------------------

_TEMP_FILE_REF = re.compile(
    r"This (?:invalid output|diff) might be helpful:\s*\S+", re.IGNORECASE
)
_UNC_PATH = re.compile(r"\\\\[\w.-]+\\[\w.-]+(?:\\[\w.-]+)*")
_WIN_PATH = re.compile(r"[A-Za-z]:\\(?:[\w.-]+\\)+[\w.-]+")
_UNIX_PATH = re.compile(r"/(?:[\w.-]+/)+[\w.-]+")


def sanitize_message(msg: str) -> str:
    """Remove absolute paths and temp-file references from *msg*."""
    msg = _TEMP_FILE_REF.sub("", msg)
    msg = _UNC_PATH.sub("<path>", msg)
    msg = _WIN_PATH.sub("<path>", msg)
    msg = _UNIX_PATH.sub("<path>", msg)
    return msg.strip()


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

_NOTEBOOK_MARKER = "cannot be parsed as valid Jupyter notebook"


def classify_failure(exc: Exception) -> Failure:
    """Classify *exc* into a :class:`Failure` with a stable error code.

    The function inspects the exception type and message text.  It uses
    ``type(exc).__name__`` for ``HeaderError`` / ``InvalidVariantHeader``
    so that importing from ``blackd`` (which requires ``aiohttp``) is not
    necessary.
    """
    cls_name = type(exc).__name__
    msg = str(exc)

    if isinstance(exc, InvalidInput):
        code = FailureCode.SYNTAX_ERROR
    elif isinstance(exc, ASTSafetyError):
        code = FailureCode.AST_EQUIVALENCE
    elif isinstance(exc, SourceASTParseError):
        code = FailureCode.AST_PARSE_FAILURE
    elif isinstance(exc, AssertionError) and "INTERNAL ERROR" in msg:
        code = FailureCode.FORMAT_INSTABILITY
    elif isinstance(exc, ValueError) and _NOTEBOOK_MARKER in msg:
        code = FailureCode.INVALID_NOTEBOOK
    elif cls_name == "InvalidVariantHeader":
        code = FailureCode.INVALID_VARIANT
    elif cls_name == "HeaderError":
        code = FailureCode.INVALID_HEADER
    else:
        code = FailureCode.UNKNOWN

    return Failure(
        code=code,
        summary=_SUMMARIES[code],
        detail=sanitize_message(msg),
    )
