---
name: backend-formatting
description: How to run Ruff to format Python files
---

# Python Formatting

We use ruff to format all Python files. We also use ./pyproject.toml to configure Ruff.

```bash
uv run ruff format --config ./pyproject.toml
```
