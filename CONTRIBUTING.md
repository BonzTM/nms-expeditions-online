# Contributing to NMS Expeditions Online

Thanks for your interest in contributing! This document covers the basics for getting started.

## Development Setup

1. Clone the repo:
   ```bash
   git clone https://github.com/BonzTM/nms-expeditions-online.git
   cd nms-expeditions-online
   ```

2. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

3. Run the tests:
   ```bash
   pytest
   ```

4. Run the linter:
   ```bash
   ruff check .
   ```

## Making Changes

1. Create a branch from `main`
2. Make your changes
3. Add or update tests as needed
4. Make sure `pytest` and `ruff check .` pass
5. Open a pull request against `main`

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Include a clear description of what changed and why
- Add tests for new functionality
- Update the README if your change affects user-facing behavior

## Reporting Bugs

Use the [bug report template](https://github.com/BonzTM/nms-expeditions-online/issues/new?template=bug_report.yml) on GitHub. Include:

- Your OS (Windows version, Linux distro, Steam Deck)
- Python version (if running from source)
- The full error output from the tool
- Steps to reproduce the issue

## Code Style

- Follow existing patterns in the codebase
- Use type hints for function signatures
- Keep dependencies minimal — think twice before adding a new package

## License

By contributing, you agree that your contributions will be licensed under the [AGPL-3.0 License](LICENSE).
