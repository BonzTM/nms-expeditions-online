"""Tests for the hosts file management module."""


from nms_expeditions_online.hosts import (
    HOSTS_ENTRIES,
    SENTINEL_END,
    SENTINEL_START,
    install,
    is_installed,
    uninstall,
)


def _patch_hosts(monkeypatch, tmp_path, content=""):
    """Create a temporary hosts file and patch the module to use it."""
    hosts_file = tmp_path / "hosts"
    hosts_file.write_text(content)
    monkeypatch.setattr(
        "nms_expeditions_online.hosts.get_hosts_path",
        lambda: str(hosts_file),
    )
    # Disable DNS cache flushing during tests
    monkeypatch.setattr(
        "nms_expeditions_online.hosts._flush_dns_cache",
        lambda: None,
    )
    return hosts_file


def test_is_installed_false(monkeypatch, tmp_path):
    _patch_hosts(monkeypatch, tmp_path, "127.0.0.1 localhost\n")
    assert is_installed() is False


def test_is_installed_true(monkeypatch, tmp_path):
    content = f"127.0.0.1 localhost\n{SENTINEL_START}\n127.0.0.1 test\n{SENTINEL_END}\n"
    _patch_hosts(monkeypatch, tmp_path, content)
    assert is_installed() is True


def test_install_adds_entries(monkeypatch, tmp_path):
    hosts_file = _patch_hosts(monkeypatch, tmp_path, "127.0.0.1 localhost\n")
    err = install()
    assert err is None
    content = hosts_file.read_text()
    assert SENTINEL_START in content
    assert SENTINEL_END in content
    for entry in HOSTS_ENTRIES:
        assert entry in content


def test_install_idempotent(monkeypatch, tmp_path):
    hosts_file = _patch_hosts(monkeypatch, tmp_path, "127.0.0.1 localhost\n")
    install()
    content_after_first = hosts_file.read_text()
    install()  # second install should be a no-op
    assert hosts_file.read_text() == content_after_first


def test_uninstall_removes_entries(monkeypatch, tmp_path):
    hosts_file = _patch_hosts(monkeypatch, tmp_path, "127.0.0.1 localhost\n")
    install()
    assert is_installed() is True
    err = uninstall()
    assert err is None
    assert is_installed() is False
    content = hosts_file.read_text()
    assert SENTINEL_START not in content
    assert SENTINEL_END not in content
    assert "127.0.0.1 localhost" in content


def test_uninstall_when_not_installed(monkeypatch, tmp_path):
    _patch_hosts(monkeypatch, tmp_path, "127.0.0.1 localhost\n")
    err = uninstall()
    assert err is None  # should be a no-op, not an error


def test_install_adds_newline_if_missing(monkeypatch, tmp_path):
    hosts_file = _patch_hosts(monkeypatch, tmp_path, "127.0.0.1 localhost")  # no trailing newline
    install()
    content = hosts_file.read_text()
    # Should not have the sentinel jammed onto the localhost line
    assert "localhost\n" in content


def test_roundtrip_preserves_existing_content(monkeypatch, tmp_path):
    original = "127.0.0.1 localhost\n::1 localhost\n"
    hosts_file = _patch_hosts(monkeypatch, tmp_path, original)
    install()
    uninstall()
    content = hosts_file.read_text()
    # Original lines should be preserved
    assert "127.0.0.1 localhost" in content
    assert "::1 localhost" in content
