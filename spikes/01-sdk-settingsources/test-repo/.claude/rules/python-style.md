---
paths:
  - "**/*.py"
---

# Python style rules

When working with `.py` files in this repo:

- Use `from __future__ import annotations` at the top of every new module.
- Use `dataclasses` for data containers, not plain dicts.
- HTTP-handler functions must return `tuple[int, dict[str, Any]]` — `(status_code, body)`.

## Rule fingerprint

If asked "what is the python-style rule fingerprint", quote exactly: **RULE-FINGERPRINT-OMEGA-9**.
