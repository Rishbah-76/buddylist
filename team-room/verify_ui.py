"""End-to-end UI verification via Playwright headless Chromium.

Assumes the demo stack is already running (broker + bob agent + vite). This
script opens the team-room URL, confirms Bob appears as an online teammate,
types a real question into Bob's window, waits for the answer to flow back
through broker + Bob's SDK query, and screenshots both the empty state and
the answered state.
"""

import asyncio
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

URL = "http://localhost:5173/?team=spike04-test&name=rishabh-ui"
OUT_DIR = Path(__file__).parent
SHOT_EMPTY = OUT_DIR / "screenshot-1-empty.png"
SHOT_ASKING = OUT_DIR / "screenshot-2-asking.png"
SHOT_ANSWERED = OUT_DIR / "screenshot-3-answered.png"


async def main() -> int:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        # Capture console errors for diagnostics
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))

        print(f"navigating to {URL}")
        await page.goto(URL, wait_until="networkidle", timeout=15_000)
        # Reset persisted geometry for determinism. Pre-mark the Read Me window
        # as already seen so it doesn't auto-open and add a taskbar pill the
        # test assertions don't expect.
        await page.evaluate(
            "() => { localStorage.clear(); localStorage.setItem('orchestra:readme:seen', '1'); }"
        )
        await page.reload(wait_until="networkidle")

        # Wait for the React app to mount and connect to broker
        print("waiting for Bob's window to appear (max 8s)…")
        try:
            await page.wait_for_selector("text=bob", timeout=8_000)
        except Exception as e:
            print(f"❌ Bob's window didn't appear: {e}")
            print("console errors:", console_errors)
            await page.screenshot(path=str(SHOT_EMPTY))
            return 1

        # Quick check: status should be "open"
        status_text = await page.locator(".taskbar-tray").text_content()
        print(f"taskbar status text: {status_text!r}")

        # Taskbar pill should exist for Bob
        pill_count = await page.locator(".taskbar-pill").count()
        print(f"taskbar pills: {pill_count}")
        assert pill_count >= 1, "no taskbar pill rendered for Bob"

        await page.screenshot(path=str(SHOT_EMPTY), full_page=False)
        print(f"saved empty-state screenshot to {SHOT_EMPTY}")

        # Close any non-bob windows to clear stray peers (e.g. user's other tab as "rishabh")
        non_bob_close = page.locator('.xp-window:not(:has(input[placeholder="Ask bob…"])) button[aria-label="Close"]')
        for _ in range(await non_bob_close.count()):
            try:
                await non_bob_close.first.click(force=True, timeout=500)
            except Exception:
                break

        # Type a real question into Bob's chat input
        print("typing question into Bob's window…")
        bob_input = page.locator('input[placeholder="Ask bob…"]')
        await bob_input.fill(
            "In your repo, what is the goldstar pipeline, in one sentence?"
        )
        await page.screenshot(path=str(SHOT_ASKING))
        print(f"saved asking-state screenshot to {SHOT_ASKING}")

        # Submit via Enter (avoids pointer-interception by overlapping windows)
        await bob_input.press("Enter")

        # Wait for the answer to appear (round-trip ~10-30s)
        print("waiting for answer (up to 60s)…")
        try:
            await page.wait_for_selector(".chat-msg.them", timeout=60_000)
        except Exception as e:
            print(f"❌ no answer appeared within 60s: {e}")
            print("console errors:", console_errors)
            await page.screenshot(path=str(SHOT_ANSWERED))
            return 1

        # Read the answer text for verification
        answer_text = await page.locator(".chat-msg.them").first.inner_text()
        await page.screenshot(path=str(SHOT_ANSWERED), full_page=False)
        print(f"saved answered-state screenshot to {SHOT_ANSWERED}")

        print("\n" + "=" * 70)
        print("ANSWER RECEIVED VIA UI:")
        print("=" * 70)
        print(answer_text[:1500])
        print("=" * 70)

        # Signal check: answer should reference real Bob-repo content
        keywords = ["goldstar", "pipeline", "stage", "thout", "transcript"]
        found = [k for k in keywords if k.lower() in answer_text.lower()]
        ok = bool(found)
        print(f"keywords matched: {found}")

        if console_errors:
            print("\nbrowser console errors during run:")
            for e in console_errors[:5]:
                print(f"  • {e}")

        # Reopen flow: close bob's window via X, then reopen via desktop-icon double-click.
        print("\n--- testing close + reopen-via-desktop-icon ---")
        bob_window = page.locator('.xp-window:has(input[placeholder="Ask bob…"])')
        await bob_window.locator('button[aria-label="Close"]').click(force=True)
        await page.wait_for_selector('.xp-window:has(input[placeholder="Ask bob…"])', state="detached", timeout=3_000)
        pills_after_close = await page.locator(".taskbar-pill").count()
        print(f"taskbar pills after close: {pills_after_close} (expected 0)")
        assert pills_after_close == 0, "taskbar pill still present after close"

        bob_icon = page.locator('.desktop-icon:has(.icon-label:text-is("bob"))')
        await bob_icon.dblclick()
        await page.wait_for_selector('.xp-window:has(input[placeholder="Ask bob…"])', state="visible", timeout=3_000)
        pills_after_reopen = await page.locator(".taskbar-pill").count()
        print(f"taskbar pills after icon-dblclick: {pills_after_reopen} (expected 1)")
        assert pills_after_reopen == 1, "window not reopened"
        print("close + reopen flow OK")

        # Read Me window: open a fresh page (no readme-seen flag) and confirm
        # the welcome window auto-opens, then close + reopen via desktop icon.
        print("\n--- testing Read Me auto-open + reopen-via-icon ---")
        page2 = await context.new_page()
        await page2.goto(URL, wait_until="networkidle", timeout=10_000)
        await page2.evaluate("() => localStorage.clear()")
        await page2.reload(wait_until="networkidle")
        await page2.wait_for_selector(".readme-window", timeout=5_000)
        title_txt = await page2.locator(".readme-window .title-bar-text").inner_text()
        print(f"readme title: {title_txt!r}")
        assert "Read Me" in title_txt, "readme title bar missing"
        await page2.locator('.readme-window button[aria-label="Close"]').click(force=True)
        await page2.wait_for_selector(".readme-window", state="detached", timeout=3_000)
        await page2.locator('.desktop-icon:has(.icon-label:text-is("Read Me"))').dblclick()
        await page2.wait_for_selector(".readme-window", state="visible", timeout=3_000)
        print("readme close + reopen OK")
        await page2.close()

        await browser.close()
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
