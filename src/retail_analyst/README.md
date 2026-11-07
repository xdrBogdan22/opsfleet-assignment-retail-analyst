# retail_analyst package

| Package | Responsibility |
|---|---|
| `core/` | Settings loaded from `config/` |
| `safety/` | The SQL guard: turns model-written SQL into scoped, read-only SQL |

Rules for code in this package:

- Data rules and limits come from settings, never from literals in code.
- Safety checks are plain functions with no model calls, so tests can prove them.
- Each module starts with a docstring that says what it guarantees.
