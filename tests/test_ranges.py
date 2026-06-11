"""Test the black.ranges module."""

import pytest

from black.ranges import (
    _normalize_line_ranges,
    adjusted_lines,
    parse_line_ranges,
    sanitized_lines,
)


@pytest.mark.parametrize(
    "lines_str, expected",
    [
        (["1-5"], [(1, 5)]),
        (["1-1"], [(1, 1)]),
        (["1-3", "5-7"], [(1, 3), (5, 7)]),
    ],
)
def test_parse_line_ranges_valid(
    lines_str: list[str], expected: list[tuple[int, int]]
) -> None:
    assert parse_line_ranges(lines_str) == expected


@pytest.mark.parametrize(
    "lines_str",
    [
        ["5-3"],
        ["0-5"],
        ["-1-5"],
        ["5-0"],
    ],
)
def test_parse_line_ranges_invalid(lines_str: list[str]) -> None:
    with pytest.raises(ValueError, match="Incorrect --line-ranges"):
        parse_line_ranges(lines_str)


@pytest.mark.parametrize(
    "lines",
    [[(1, 1)], [(1, 3)], [(1, 1), (3, 4)]],
)
def test_no_diff(lines: list[tuple[int, int]]) -> None:
    source = """\
import re

def func():
pass
"""
    assert lines == adjusted_lines(lines, source, source)


@pytest.mark.parametrize(
    "lines",
    [
        [(1, 0)],
        [(-8, 0)],
        [(-8, 8)],
        [(1, 100)],
        [(2, 1)],
        [(0, 8), (3, 1)],
    ],
)
def test_invalid_lines(lines: list[tuple[int, int]]) -> None:
    original_source = """\
import re
def foo(arg):
'''This is the foo function.

This is foo function's
docstring with more descriptive texts.
'''

def func(arg1,
arg2, arg3):
pass
"""
    modified_source = """\
import re
def foo(arg):
'''This is the foo function.

This is foo function's
docstring with more descriptive texts.
'''

def func(arg1, arg2, arg3):
pass
"""
    assert not adjusted_lines(lines, original_source, modified_source)


@pytest.mark.parametrize(
    "lines,adjusted",
    [
        (
            [(1, 1)],
            [(1, 1)],
        ),
        (
            [(1, 2)],
            [(1, 1)],
        ),
        (
            [(1, 6)],
            [(1, 2)],
        ),
        (
            [(6, 6)],
            [],
        ),
    ],
)
def test_removals(
    lines: list[tuple[int, int]], adjusted: list[tuple[int, int]]
) -> None:
    original_source = """\
1. first line
2. second line
3. third line
4. fourth line
5. fifth line
6. sixth line
"""
    modified_source = """\
2. second line
5. fifth line
"""
    assert adjusted == adjusted_lines(lines, original_source, modified_source)


@pytest.mark.parametrize(
    "lines,adjusted",
    [
        (
            [(1, 1)],
            [(2, 2)],
        ),
        (
            [(1, 2)],
            [(2, 5)],
        ),
        (
            [(2, 2)],
            [(5, 5)],
        ),
    ],
)
def test_additions(
    lines: list[tuple[int, int]], adjusted: list[tuple[int, int]]
) -> None:
    original_source = """\
1. first line
2. second line
"""
    modified_source = """\
this is added
1. first line
this is added
this is added
2. second line
this is added
"""
    assert adjusted == adjusted_lines(lines, original_source, modified_source)


@pytest.mark.parametrize(
    "lines,adjusted",
    [
        (
            [(1, 11)],
            [(1, 10)],
        ),
        (
            [(1, 12)],
            [(1, 11)],
        ),
        (
            [(10, 10)],
            [(9, 9)],
        ),
        ([(1, 1), (9, 10)], [(1, 1), (9, 9)]),
        ([(9, 10), (1, 1)], [(1, 1), (9, 9)]),
    ],
)
def test_diffs(lines: list[tuple[int, int]], adjusted: list[tuple[int, int]]) -> None:
    original_source = """\
 1. import re
 2. def foo(arg):
 3.   '''This is the foo function.
 4.
 5.   This is foo function's
 6.   docstring with more descriptive texts.
 7.   '''
 8.
 9. def func(arg1,
10.   arg2, arg3):
11.   pass
12. # last line
"""
    modified_source = """\
 1. import re  # changed
 2. def foo(arg):
 3.   '''This is the foo function.
 4.
 5.   This is foo function's
 6.   docstring with more descriptive texts.
 7.   '''
 8.
 9. def func(arg1, arg2, arg3):
11.   pass
12. # last line changed
"""
    assert adjusted == adjusted_lines(lines, original_source, modified_source)


@pytest.mark.parametrize(
    "lines,sanitized",
    [
        (
            [(1, 4)],
            [(1, 4)],
        ),
        (
            [(2, 3)],
            [(2, 3)],
        ),
        (
            [(2, 10)],
            [(2, 4)],
        ),
        (
            [(0, 3)],
            [(1, 3)],
        ),
        (
            [(0, 10)],
            [(1, 4)],
        ),
        (
            [(-2, 3)],
            [(1, 3)],
        ),
        (
            [(0, 0)],
            [],
        ),
        (
            [(-2, -1)],
            [],
        ),
        (
            [(-1, 0)],
            [],
        ),
        (
            [(3, 1), (1, 3), (5, 6)],
            [(1, 3)],
        ),
    ],
)
def test_sanitize(
    lines: list[tuple[int, int]], sanitized: list[tuple[int, int]]
) -> None:
    source = """\
1. import re
2. def func(arg1,
3.   arg2, arg3):
4.   pass
"""
    assert sanitized == sanitized_lines(lines, source)

    source_no_trailing_nl = """\
    1. import re
    2. def func(arg1,
    3.   arg2, arg3):
    4.   pass"""
    assert sanitized == sanitized_lines(lines, source_no_trailing_nl)


@pytest.mark.parametrize(
    "ranges,expected",
    [
        # Empty
        ([], []),
        # Single range
        ([(1, 5)], [(1, 5)]),
        # Disjoint, already sorted
        ([(1, 3), (5, 7)], [(1, 3), (5, 7)]),
        # Overlapping
        ([(1, 5), (3, 8)], [(1, 8)]),
        # Adjacent (end == next_start - 1)
        ([(1, 3), (4, 6)], [(1, 6)]),
        # Contained
        ([(1, 10), (3, 5)], [(1, 10)]),
        # Unordered
        ([(5, 7), (1, 3)], [(1, 3), (5, 7)]),
        # Unordered + overlapping
        ([(8, 12), (1, 5), (3, 9)], [(1, 12)]),
        # Multiple merges
        ([(1, 2), (3, 4), (5, 6), (10, 12)], [(1, 6), (10, 12)]),
        # Duplicate ranges
        ([(1, 5), (1, 5)], [(1, 5)]),
        # Touching at a single point
        ([(1, 3), (3, 5)], [(1, 5)]),
    ],
)
def test_normalize_line_ranges(
    ranges: list[tuple[int, int]], expected: list[tuple[int, int]]
) -> None:
    assert expected == _normalize_line_ranges(ranges)


@pytest.mark.parametrize(
    "lines,sanitized",
    [
        # Overlapping ranges get merged after clamping
        (
            [(1, 3), (2, 4)],
            [(1, 4)],
        ),
        # Adjacent ranges get merged
        (
            [(1, 2), (3, 4)],
            [(1, 4)],
        ),
        # Unordered + overlapping
        (
            [(3, 4), (1, 3)],
            [(1, 4)],
        ),
        # Overlapping, one extends past source
        (
            [(1, 3), (2, 100)],
            [(1, 4)],
        ),
        # Multiple disjoint stay disjoint
        (
            [(1, 1), (3, 4)],
            [(1, 1), (3, 4)],
        ),
    ],
)
def test_sanitize_with_overlapping(
    lines: list[tuple[int, int]], sanitized: list[tuple[int, int]]
) -> None:
    source = """\
1. import re
2. def func(arg1,
3.   arg2, arg3):
4.   pass
"""
    assert sanitized == sanitized_lines(lines, source)


@pytest.mark.parametrize(
    "lines,adjusted",
    [
        # Two adjacent ranges that both expand into the same diff block
        # should be merged into a single range.
        (
            [(9, 10), (10, 11)],
            [(9, 10)],
        ),
        # Overlapping ranges that span a diff block
        (
            [(9, 10), (9, 11)],
            [(9, 10)],
        ),
        # Unordered input covering the same region
        (
            [(10, 11), (9, 10)],
            [(9, 10)],
        ),
        # Disjoint ranges, one hits a diff block, they stay separate
        (
            [(1, 1), (10, 11)],
            [(1, 1), (9, 10)],
        ),
    ],
)
def test_adjusted_lines_with_overlapping(
    lines: list[tuple[int, int]], adjusted: list[tuple[int, int]]
) -> None:
    original_source = """\
 1. import re
 2. def foo(arg):
 3.   '''This is the foo function.
 4.
 5.   This is foo function's
 6.   docstring with more descriptive texts.
 7.   '''
 8.
 9. def func(arg1,
10.   arg2, arg3):
11.   pass
12. # last line
"""
    modified_source = """\
 1. import re  # changed
 2. def foo(arg):
 3.   '''This is the foo function.
 4.
 5.   This is foo function's
 6.   docstring with more descriptive texts.
 7.   '''
 8.
 9. def func(arg1, arg2, arg3):
11.   pass
12. # last line changed
"""
    assert adjusted == adjusted_lines(lines, original_source, modified_source)
