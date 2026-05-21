"""Cloudflare Tunnel wrapper.

Wraps the `cloudflared tunnel --url <target>` command, parses the temporary
trycloudflare.com URL out of the stderr stream, and prints it back to the
operator. The tunnel stays alive in the foreground until Ctrl-C.

No Cloudflare account or login is needed for these "quick tunnels". The URL is
freshly assigned each time and expires when the tunnel closes.
"""

from __future__ import annotations

import re
import shutil
import signal
import subprocess
import sys
from typing import Optional

TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

_INSTALL_HINT = (
    "error: 'cloudflared' is not installed or not on PATH.\n"
    "  macOS:        brew install cloudflared\n"
    "  Debian/Ubuntu: see https://pkg.cloudflare.com/index.html\n"
    "  Windows:      winget install --id Cloudflare.cloudflared\n"
)


def _https_to_wss(url: str) -> str:
    return url.replace("https://", "wss://", 1).rstrip("/") + "/"


def run_tunnel(target_url: str = "http://localhost:8765") -> int:
    """Start a Cloudflare quick tunnel pointing at `target_url`.

    Blocks until cloudflared exits or Ctrl-C is received. Returns the exit code.
    """
    if not shutil.which("cloudflared"):
        sys.stderr.write(_INSTALL_HINT)
        return 127

    cmd = ["cloudflared", "tunnel", "--no-autoupdate", "--url", target_url]
    print(f"[tunnel] starting: {' '.join(cmd)}", file=sys.stderr, flush=True)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    public_url: Optional[str] = None

    def _shutdown(_signum, _frame):
        proc.terminate()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stderr.write(line)
            sys.stderr.flush()
            if public_url is None:
                m = TUNNEL_URL_RE.search(line)
                if m:
                    public_url = m.group(0)
                    wss = _https_to_wss(public_url)
                    banner = (
                        "\n"
                        "  ══════════════════════════════════════════════════════════════════\n"
                        "    Orchestra broker is now reachable from the public internet.\n"
                        "      public HTTPS : " + public_url + "\n"
                        "      broker WSS   : " + wss + "\n"
                        "    Teammates can join with:\n"
                        "      orchestra agent --team <CODE> --as <NAME> \\\n"
                        "        --broker " + wss + " --repo /path/to/repo\n"
                        "  ══════════════════════════════════════════════════════════════════\n"
                        "\n"
                    )
                    print(banner, flush=True)
    finally:
        proc.terminate()
        proc.wait()
    return proc.returncode or 0


def extract_url_from_output(stream) -> Optional[str]:
    """Helper for tests / programmatic use: scan a text stream for the first
    trycloudflare.com URL and return it."""
    for line in stream:
        m = TUNNEL_URL_RE.search(line)
        if m:
            return m.group(0)
    return None


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
    sys.exit(run_tunnel(target))


def main() -> None:
    """Entry point for `orchestra-tunnel` console script."""
    target = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8765"
    sys.exit(run_tunnel(target))
