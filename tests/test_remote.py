import pytest

import lieer


class MockConfig:
    account = "me"
    ignore_remote_labels = []
    ignore_empty_history = False


class MockLocal:
    loaded = True

    def __init__(self):
        self.config = MockConfig()


class MockRemoteGmi:
    dry_run = False
    verbose = False
    credentials_file = None

    def __init__(self):
        self.local = MockLocal()


class MockHistory:
    """Serves history pages by page token and counts the requests."""

    def __init__(self, pages):
        self.pages = pages
        self.requests = 0

    def list(self, userId, startHistoryId, pageToken=None):
        self.requests += 1
        assert self.requests < 10, "history pages requested in a loop"
        page = self.pages[pageToken]
        return type("Request", (), {"execute": lambda _self: page})()


class MockService:
    def __init__(self, history):
        self._history = history

    def users(self):
        return self

    def history(self):
        return self._history


def remote_with_pages(pages, ignore_empty_history):
    g = MockRemoteGmi()
    g.local.config.ignore_empty_history = ignore_empty_history
    r = lieer.Remote(g)
    r.authorized = True
    r.service = MockService(MockHistory(pages))
    return r


def test_history_follows_pages():
    pages = {
        None: {"history": [{"id": "1"}], "nextPageToken": "a"},
        "a": {"history": [{"id": "2"}]},
    }
    r = remote_with_pages(pages, False)
    assert list(r.get_history_since(1)) == [[{"id": "1"}], [{"id": "2"}]]


def test_empty_history_page_fails_by_default():
    pages = {
        None: {"history": [{"id": "1"}], "nextPageToken": "a"},
        "a": {},
    }
    r = remote_with_pages(pages, False)
    with pytest.raises(lieer.Remote.NoHistoryException):
        list(r.get_history_since(1))


def test_ignored_empty_last_page_ends():
    pages = {
        None: {"history": [{"id": "1"}], "nextPageToken": "a"},
        "a": {},
    }
    r = remote_with_pages(pages, True)
    assert list(r.get_history_since(1)) == [[{"id": "1"}]]
    assert r.service.history().requests == 2


def test_ignored_empty_page_continues_to_next():
    pages = {
        None: {"history": [{"id": "1"}], "nextPageToken": "a"},
        "a": {"nextPageToken": "b"},
        "b": {"history": [{"id": "2"}]},
    }
    r = remote_with_pages(pages, True)
    assert list(r.get_history_since(1)) == [[{"id": "1"}], [{"id": "2"}]]
