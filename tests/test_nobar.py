import pytest

from lieer.nobar import tqdm


def test_iteration_without_iterable_raises_stop_iteration():
    with pytest.raises(StopIteration):
        next(tqdm(desc="x"))


def test_iteration_over_iterable():
    assert list(tqdm([1, 2, 3])) == [1, 2, 3]
