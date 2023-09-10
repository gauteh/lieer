import pytest
import lieer


def test_update_translation_list(gmi):
    l = lieer.Local(gmi)
    l.update_translation_list_with_overlay(["a", "1", "b", "2"])
    assert l.translate_labels["a"] == "1"
    assert l.translate_labels["b"] == "2"
    assert l.labels_translate["1"] == "a"
    assert l.labels_translate["2"] == "b"

    with pytest.raises(Exception):
        l.update_translation_list_with_overlay(["a", "1", "b", "2", "c"])
