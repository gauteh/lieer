"""
Tests for ignore_tags_regex_local functionality
"""

import json
import os
import tempfile
from types import MethodType

import pytest

from lieer.local import Local


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = os.path.join(tmpdir, ".gmailieer.json")
        yield config_file


@pytest.fixture
def fake_local(temp_config_file):
    """Create a fake Local instance for testing regex matching"""

    class FakeLocal:
        pass

    def create_with_patterns(patterns):
        test_config = {"account": "test@example.com", "ignore_tags_regex": patterns}
        with open(temp_config_file, "w") as f:
            json.dump(test_config, f)

        fake = FakeLocal()
        fake.config = Local.Config(temp_config_file)
        fake.matches_ignore_regex = MethodType(Local.matches_ignore_regex, fake)
        return fake

    return create_with_patterns


def test_regex_patterns_load_and_compile(temp_config_file):
    """Test that regex patterns load from config and compile correctly"""
    test_config = {
        "account": "test@example.com",
        "ignore_tags_regex": ["^draft-.*", "temp-.*", "work/.*"],
    }

    with open(temp_config_file, "w") as f:
        json.dump(test_config, f)

    config = Local.Config(temp_config_file)

    assert len(config.ignore_tags_regex) == 3
    assert len(config._compiled_ignore_regex) == 3


def test_invalid_regex_patterns_skipped(temp_config_file):
    """Test that invalid regex patterns generate warnings but don't fail"""
    test_config = {
        "account": "test@example.com",
        "ignore_tags_regex": ["^draft-.*", "[invalid(", "valid-pattern"],
    }

    with open(temp_config_file, "w") as f:
        json.dump(test_config, f)

    config = Local.Config(temp_config_file)

    # Only valid patterns should be compiled
    assert len(config._compiled_ignore_regex) == 2
    assert "^draft-.*" in config.ignore_tags_regex
    assert "valid-pattern" in config.ignore_tags_regex
    assert "[invalid(" not in config.ignore_tags_regex


def test_regex_matching_patterns(fake_local):
    """Test matching various regex patterns (prefix, suffix, contains)"""
    local = fake_local(["^draft-.*", ".*-temp$", "work/.*"])

    # Prefix match
    assert local.matches_ignore_regex("draft-v1")
    assert not local.matches_ignore_regex("my-draft")

    # Suffix match
    assert local.matches_ignore_regex("file-temp")
    assert not local.matches_ignore_regex("temp-file")

    # Contains match
    assert local.matches_ignore_regex("work/project")
    assert not local.matches_ignore_regex("homework")

    # No match
    assert not local.matches_ignore_regex("normal-tag")


def test_regex_matching_case_sensitive(fake_local):
    """Test that regex matching is case-sensitive"""
    local = fake_local(["^draft-.*"])

    assert local.matches_ignore_regex("draft-v1")
    assert not local.matches_ignore_regex("Draft-v1")


def test_setter_method_persistence(temp_config_file):
    """Test that setter method works and persists to config"""
    test_config = {"account": "test@example.com"}

    with open(temp_config_file, "w") as f:
        json.dump(test_config, f)

    config = Local.Config(temp_config_file)
    config.set_ignore_tags_regex("^draft-.*,temp-.*")

    assert len(config.ignore_tags_regex) == 2
    assert len(config._compiled_ignore_regex) == 2

    # Reload to verify persistence
    config2 = Local.Config(temp_config_file)
    assert len(config2.ignore_tags_regex) == 2
    assert "^draft-.*" in config2.ignore_tags_regex


def test_setter_method_clears_patterns(temp_config_file):
    """Test that empty string clears patterns"""
    test_config = {
        "account": "test@example.com",
        "ignore_tags_regex": ["^draft-.*"],
    }

    with open(temp_config_file, "w") as f:
        json.dump(test_config, f)

    config = Local.Config(temp_config_file)
    config.set_ignore_tags_regex("")

    assert len(config.ignore_tags_regex) == 0
    assert len(config._compiled_ignore_regex) == 0
