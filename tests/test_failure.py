"""Tests for Black's failure classification system."""

from dataclasses import FrozenInstanceError
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

import black
from black.failure import (
    Failure,
    FailureCode,
    classify_failure,
    sanitize_message,
)
from black.parsing import ASTSafetyError, InvalidInput, SourceASTParseError
from black.report import Report


# -----------------------------------------------------------------------
# Classification tests — one per FailureCode
# -----------------------------------------------------------------------


class TestClassifyFailure:
    def test_syntax_error(self) -> None:
        exc = InvalidInput("Cannot parse: 1:6\n    print(\n         ^")
        failure = classify_failure(exc)
        assert failure.code is FailureCode.SYNTAX_ERROR
        assert failure.code.value == 100
        assert "syntax" in failure.summary.lower()
        assert "Cannot parse" in failure.detail

    def test_ast_equivalence(self) -> None:
        exc = ASTSafetyError(
            "INTERNAL ERROR: Black produced code that is not equivalent to the source"
        )
        failure = classify_failure(exc)
        assert failure.code is FailureCode.AST_EQUIVALENCE
        assert failure.code.value == 101
        assert "AST-equivalent" in failure.summary

    def test_ast_parse_failure(self) -> None:
        exc = SourceASTParseError(
            "cannot use --safe with this file; failed to parse source file AST"
        )
        failure = classify_failure(exc)
        assert failure.code is FailureCode.AST_PARSE_FAILURE
        assert failure.code.value == 102
        assert "ast.parse()" in failure.summary

    def test_format_instability(self) -> None:
        exc = AssertionError(
            "INTERNAL ERROR: Black produced different code on the second pass."
        )
        failure = classify_failure(exc)
        assert failure.code is FailureCode.FORMAT_INSTABILITY
        assert failure.code.value == 103
        assert "stable" in failure.summary.lower()

    def test_assertion_error_without_internal_error_is_unknown(self) -> None:
        exc = AssertionError("some other assertion")
        failure = classify_failure(exc)
        assert failure.code is FailureCode.UNKNOWN

    def test_invalid_notebook(self) -> None:
        exc = ValueError(
            "File '/home/user/nb.ipynb' cannot be parsed as valid Jupyter notebook."
        )
        failure = classify_failure(exc)
        assert failure.code is FailureCode.INVALID_NOTEBOOK
        assert failure.code.value == 200
        assert "Jupyter" in failure.summary
        # Path should be sanitized
        assert "/home/user" not in failure.detail

    def test_valueerror_without_notebook_marker_is_unknown(self) -> None:
        exc = ValueError("some other value error")
        failure = classify_failure(exc)
        assert failure.code is FailureCode.UNKNOWN

    def test_header_error(self) -> None:
        # Simulate HeaderError without importing from blackd (needs aiohttp)
        HeaderError = type("HeaderError", (Exception,), {})
        exc = HeaderError("Invalid line length header value")
        failure = classify_failure(exc)
        assert failure.code is FailureCode.INVALID_HEADER
        assert failure.code.value == 300

    def test_invalid_variant_header(self) -> None:
        InvalidVariantHeader = type("InvalidVariantHeader", (Exception,), {})
        exc = InvalidVariantHeader("Unknown Python variant: py2.7")
        failure = classify_failure(exc)
        assert failure.code is FailureCode.INVALID_VARIANT
        assert failure.code.value == 301

    def test_unknown_error(self) -> None:
        exc = RuntimeError("something went wrong")
        failure = classify_failure(exc)
        assert failure.code is FailureCode.UNKNOWN
        assert failure.code.value == 900
        assert "unexpected" in failure.summary.lower()
        assert "something went wrong" in failure.detail

    def test_unknown_oserror(self) -> None:
        exc = OSError("Permission denied")
        failure = classify_failure(exc)
        assert failure.code is FailureCode.UNKNOWN

    def test_detail_is_always_sanitized(self) -> None:
        exc = InvalidInput(
            "Cannot parse: /home/user/secret/code.py:1:6"
        )
        failure = classify_failure(exc)
        assert "/home/user" not in failure.detail


# -----------------------------------------------------------------------
# Privacy / sanitization tests
# -----------------------------------------------------------------------


class TestSanitizeMessage:
    def test_unix_path(self) -> None:
        msg = "error in /home/user/project/file.py at line 5"
        result = sanitize_message(msg)
        assert "/home/user" not in result
        assert "<path>" in result
        assert "at line 5" in result

    def test_windows_path(self) -> None:
        msg = r"error in C:\Users\name\project\file.py at line 5"
        result = sanitize_message(msg)
        assert "Users" not in result
        assert "<path>" in result

    def test_unc_path(self) -> None:
        msg = r"error in \\server\share\project\file.py"
        result = sanitize_message(msg)
        assert "\\\\server" not in result
        assert "<path>" in result

    def test_temp_file_reference(self) -> None:
        msg = (
            "INTERNAL ERROR: Black produced invalid code: SyntaxError. "
            "This invalid output might be helpful: /tmp/blk_abc123.log"
        )
        result = sanitize_message(msg)
        assert "/tmp/" not in result
        assert "blk_abc" not in result
        assert "INTERNAL ERROR" in result

    def test_diff_file_reference(self) -> None:
        msg = (
            "INTERNAL ERROR: Black produced different code. "
            "This diff might be helpful: /tmp/blk_xyz789.log"
        )
        result = sanitize_message(msg)
        assert "/tmp/" not in result
        assert "INTERNAL ERROR" in result

    def test_preserves_non_path_content(self) -> None:
        msg = "Cannot parse: 1:6: unexpected token"
        result = sanitize_message(msg)
        assert result == msg

    def test_multiple_paths(self) -> None:
        msg = "diff /home/a/x.py /home/b/y.py"
        result = sanitize_message(msg)
        assert "/home/" not in result
        assert result.count("<path>") == 2

    def test_empty_string(self) -> None:
        assert sanitize_message("") == ""

    def test_simple_message(self) -> None:
        msg = "Cannot parse: 1:0"
        assert sanitize_message(msg) == msg


# -----------------------------------------------------------------------
# Stability tests — error code values must never change
# -----------------------------------------------------------------------


class TestFailureCodeStability:
    def test_code_values_are_stable(self) -> None:
        """Error code numeric values are part of the public API."""
        assert FailureCode.SYNTAX_ERROR == 100
        assert FailureCode.AST_EQUIVALENCE == 101
        assert FailureCode.AST_PARSE_FAILURE == 102
        assert FailureCode.FORMAT_INSTABILITY == 103
        assert FailureCode.INVALID_NOTEBOOK == 200
        assert FailureCode.INVALID_HEADER == 300
        assert FailureCode.INVALID_VARIANT == 301
        assert FailureCode.UNKNOWN == 900

    def test_failure_is_frozen(self) -> None:
        failure = Failure(
            code=FailureCode.UNKNOWN,
            summary="test",
            detail="test",
        )
        with pytest.raises(FrozenInstanceError):
            failure.code = FailureCode.SYNTAX_ERROR  # type: ignore[misc]

    def test_failure_code_is_int(self) -> None:
        """FailureCode values can be used directly as integers."""
        assert isinstance(FailureCode.SYNTAX_ERROR, int)
        assert FailureCode.SYNTAX_ERROR + 0 == 100


# -----------------------------------------------------------------------
# Integration tests — real parsing + Report
# -----------------------------------------------------------------------


class TestIntegration:
    def test_classify_real_parse_error(self) -> None:
        """Classification works with a real parse failure from lib2to3."""
        with pytest.raises(InvalidInput) as exc_info:
            black.lib2to3_parse("what even ( is", set())
        failure = classify_failure(exc_info.value)
        assert failure.code is FailureCode.SYNTAX_ERROR
        assert "Cannot parse" in failure.detail

    def test_report_failed_with_exception(self) -> None:
        report = Report()
        exc = InvalidInput("Cannot parse: 1:0")
        with patch("black.report.err") as mock_err:
            report.failed(Path("test.py"), str(exc), exc=exc)
        assert report.failure_count == 1
        output = mock_err.call_args[0][0]
        assert "[SYNTAX_ERROR]" in output
        assert "syntax" in output.lower()

    def test_report_failed_without_exception_backward_compat(self) -> None:
        """Existing callers that pass only a message still work."""
        report = Report()
        with patch("black.report.err") as mock_err:
            report.failed(Path("test.py"), "some error message")
        assert report.failure_count == 1
        output = mock_err.call_args[0][0]
        assert "some error message" in output
        # No error code bracket when exc is not provided
        assert "[" not in output

    def test_report_failed_with_unknown_exception(self) -> None:
        report = Report()
        exc = RuntimeError("boom")
        with patch("black.report.err") as mock_err:
            report.failed(Path("x.py"), str(exc), exc=exc)
        assert report.failure_count == 1
        output = mock_err.call_args[0][0]
        assert "[UNKNOWN]" in output

    def test_summary_never_empty(self) -> None:
        """Every FailureCode has a non-empty summary."""
        for code in FailureCode:
            exc = RuntimeError("test")
            # Force a specific code by building a Failure directly
            failure = Failure(code=code, summary="", detail="")
            # But classify_failure always fills summary from _SUMMARIES
            # So test via classify on the most generic case
        # All codes must have entries in _SUMMARIES
        from black.failure import _SUMMARIES

        for code in FailureCode:
            assert code in _SUMMARIES
            assert len(_SUMMARIES[code]) > 0
