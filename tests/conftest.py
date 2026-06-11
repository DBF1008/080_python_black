import pytest

pytest_plugins = ["tests.optional"]

PRINT_FULL_TREE: bool = False
PRINT_TREE_DIFF: bool = True


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--print-full-tree",
        action="store_true",
        default=False,
        help="print full syntax trees on failed tests",
    )
    parser.addoption(
        "--print-tree-diff",
        action="store_true",
        default=True,
        help="print diff of syntax trees on failed tests",
    )


def pytest_configure(config: pytest.Config) -> None:
    global PRINT_FULL_TREE
    global PRINT_TREE_DIFF
    PRINT_FULL_TREE = config.getoption("--print-full-tree")
    PRINT_TREE_DIFF = config.getoption("--print-tree-diff")


@pytest.fixture(autouse=True)
def _clear_black_caches():
    """Ensure file caches don't leak between tests."""
    yield
    try:
        from black.files import invalidate_caches

        invalidate_caches()
    except ImportError:
        pass
