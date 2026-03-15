"""Tests for platform utility functions."""

from nms_expeditions_online.platform_utils import get_hosts_path, is_windows


def test_get_hosts_path_returns_string():
    path = get_hosts_path()
    assert isinstance(path, str)
    assert len(path) > 0


def test_is_windows_returns_bool():
    assert isinstance(is_windows(), bool)
