# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Setup

This is a Python 3.13.5 project managed exclusively with `uv`.

### Python Version and Environment
- CPython version: `3.13.5`
- Install and pin: `uv python install 3.13.5 && uv python pin 3.13.5`

### Dependency Management
- Use `uv` exclusively; never use `pip`, `pip-tools`, or `poetry`
- Add dependencies: `uv add <package>`
- Remove dependencies: `uv remove <package>`
- Sync from lock: `uv sync`
- Run scripts: `uv run script.py` or `uv run -m package.module`

### Project Scripts
If `pyproject.toml` defines `[tool.uv.scripts]`, run them via:
- `uv run lint` - Format and lint code
- `uv run test` - Run tests
- `uv run run` - Run the main application

## Code Quality

### Ruff (Single Formatter and Linter)
- Format: `ruff format`
- Lint: `ruff check --fix`
- Configuration in `pyproject.toml` targets Python 3.13 with 88-char line length

### Python Style (TestDriven.io Clean Code)
- Use 4-space indentation, 88-char line length
- Naming: `CamelCase` classes, `snake_case` functions/variables, `UPPER_SNAKE_CASE` constants
- Functions: small, single-purpose, ≤3-5 arguments, prefer pure functions
- Prefer comprehensions, `enumerate`, `zip`, and generators over manual loops
- Use `dataclasses` for simple data containers
- Context managers (`with`) for resource management
- Catch specific exceptions; avoid bare `except`
- Docstrings for public APIs; avoid leaving commented-out code

### Python 3.13 Features
Leverage when they improve clarity/performance:
- Enhanced typing (`typing.override`)
- `match` statements for structured control flow
- F-string and interpreter improvements

## Git Commit Messages (Conventional Commits v1.0.0)

Format: `<type>(<scope>)!: <subject>`

### Types
- `feat`: new functionality
- `fix`: bug fix
- `docs`: documentation only
- `refactor`: code change without fixing bugs or adding features
- `perf`: performance improvement
- `test`: test changes only
- `build`: build system or dependency changes (use `build(deps): ...` for `uv` updates)
- `ci`: CI configuration
- `chore`: routine maintenance
- `revert`: revert previous commit

### Rules
- Subject: imperative mood, ≤50 chars, no period
- Body: wrap at 72 chars, explain why (not how)
- Breaking changes: append `!` after scope and/or add `BREAKING CHANGE:` footer
- Reference issues: `Closes #123`, `Fixes #123`, or `Refs #123`
- Atomic commits: one logical change per commit

## ByteRover MCP Tools

When using ByteRover MCP server tools:

### `byterover-store-knowledge`
Use when:
- Learning new patterns, APIs, or architectural decisions
- Finding error solutions or debugging techniques
- Discovering reusable code patterns or utility functions
- Completing significant tasks or implementations

### `byterover-retrieve-knowledge`
Use when:
- Starting new tasks or implementations
- Making architectural decisions
- Debugging issues
- Working with unfamiliar codebase areas