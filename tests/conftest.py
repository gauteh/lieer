import pytest


class MockGmi:
    dry_run = False
    verbose = False

    def __init__(self):
        pass


@pytest.fixture
def gmi():
    """
    Test gmi
    """

    return MockGmi()
