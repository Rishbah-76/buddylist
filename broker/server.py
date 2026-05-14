"""Back-compat shim — the real broker now lives in `orchestra.broker`.

Prefer `orchestra broker` (or `orchestra broker --tunnel`) for new uses.
This file is kept so existing scripts and docs that reference the path
`orchestra-poc/broker/server.py` still work.
"""

from __future__ import annotations

if __name__ == "__main__":
    from orchestra.broker import cli_main

    cli_main()
