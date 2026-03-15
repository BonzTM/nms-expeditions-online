# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.1.1] - 2026-03-15

### Added

- Test suite with 30 tests covering DNS resolution, hosts file management, proxy HTTP parsing, and response modification
- CI workflow (GitHub Actions) running pytest and ruff on Python 3.10/3.11/3.12
- `CONTRIBUTING.md` with development setup and PR guidelines
- `SECURITY.md` with vulnerability reporting process and security scope
- `CODE_OF_CONDUCT.md` (Contributor Covenant v2.1)
- GitHub issue templates (bug report, feature request) and pull request template
- Ruff linting and pytest configuration in `pyproject.toml`
- Dev dependencies (`pytest`, `ruff`) as optional `[dev]` extras
- README badges (license, CI status, latest release)

### Security

- Proxy now binds to `127.0.0.1` instead of `0.0.0.0` — no longer reachable from other machines on the network
- Added connection limits (max 32 concurrent) and body size caps (64 KB headers, 10 MB body) to prevent resource exhaustion
- Windows system commands (`certutil`, `ipconfig`) now use absolute paths to System32, preventing DLL/exe search-order hijacking
- Hosts file writes are now atomic (temp file + rename) to prevent corruption from interrupted writes or concurrent edits
- `run.sh` no longer runs `pip` as root or passes `-E` to sudo, preventing environment-based package source hijacking

### Changed

- Pinned `cryptography` dependency to `>=42,<45` (was unpinned)
- Added type hints to all functions missing return annotations
- Fixed lint issues (semicolons, line length, ambiguous variable names, unused imports, unsorted imports)
- Linux release tarball now includes `pyproject.toml` and `run.sh`
- Added `authors`, `urls`, and `classifiers` to `pyproject.toml`
- Expanded `.gitignore` with OS files, IDE directories, and virtual environments

## [1.1.0] - 2026-03-15

### Added

- Windows CA certificate installation into Trusted Root store via `certutil` for SChannel compatibility
- Self-test/verification on startup to confirm DNS redirects and TLS handshake
- Architecture diagrams (dark mode)
- Security transparency section in README for Windows users (unsigned exe, CA cert, hosts file, admin privileges, antivirus)
- Disclaimer section in README
- Table of contents in README

### Changed

- License changed from MIT to AGPL-3.0
- Certificate validity set to 48 hours (CA, server cert, and CRL) to support overnight proxy sessions

## [1.0.0] - 2025-03-15

### Added

- Local HTTPS reverse proxy for intercepting NMS expedition/season data
- Hosts file management (install/uninstall) with sentinel markers
- Direct DNS resolution bypassing the system resolver (avoids hosts file loop)
- Ephemeral CA and server certificate generation (in-memory keys)
- Linux/Steam Deck support: works with Proton/Wine without CA installation
- Interactive text-based menu (install, run, uninstall, exit)
- Multiple expedition JSON file selection
- Full multiplayer support (Steam P2P networking is unaffected)
- GitHub Actions release workflow (Windows `.exe` via PyInstaller, Linux tarball)
- `run.sh` convenience script for Linux with dependency auto-install
