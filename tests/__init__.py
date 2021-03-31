import pytest
import tempfile

class MockGmi:
    dry_run = False

    def __init__(self):
        pass



@pytest.fixture
def gmi():
    """
    Test gmi
    """

    return MockGmi()
