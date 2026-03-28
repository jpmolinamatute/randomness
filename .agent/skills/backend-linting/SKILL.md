---
name: backend-linting
description: How to run Ruff to lint python files
---

# Python Linting

We use ruff to lint all Python files. We also use ./pyproject.toml to configure Ruff.

```bash
uv run ruff check --fix --config ./pyproject.toml
```
