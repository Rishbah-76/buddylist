"""Back-compat shim — the real agent now lives in `orchestra.agent`.

This file exists so the four spike scripts (and any .mcp.json that points at
`agent/orchestra_agent.py`) keep working unchanged. Prefer the new CLI:

  orchestra agent --config bob.json
  orchestra agent --team T --as N --broker URL --repo PATH

This shim simply re-exposes the original main() and delegates to it.
"""

from __future__ import annotations

if __name__ == "__main__":
    from orchestra.agent import main

    main()
