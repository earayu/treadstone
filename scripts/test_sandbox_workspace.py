"""Validate the real workspace UI on the GitHub runner, using the image's browser."""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def main() -> None:
    output = Path("/tmp/workspace-validation")
    output.mkdir(exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path="/usr/local/bin/browser",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            for width, height in ((1440, 900), (390, 844)):
                page = await browser.new_page(viewport={"width": width, "height": height})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto("http://127.0.0.1:8080/")
                assert await page.get_by_role("tab").all_text_contents() == ["Browser", "Terminal"]
                iframe = await page.query_selector("#browser")
                frame = await iframe.content_frame()
                try:
                    await frame.locator("html.noVNC_connected").wait_for()
                    await frame.locator("#noVNC_transition").wait_for(state="hidden")
                    await frame.wait_for_function(
                        """() => {
                          const canvas = document.querySelector('canvas');
                          if (!canvas || canvas.width < 800) return false;
                          const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
                          for (let i = 4; i < pixels.length; i += 400) {
                            if (pixels[i] !== pixels[0] || pixels[i + 1] !== pixels[1]) return true;
                          }
                          return false;
                        }""",
                        timeout=60000,
                    )
                    await frame.locator("canvas").click(position={"x": 150, "y": 150})
                    await page.keyboard.press("F6")
                    # VNC key delivery precedes the remote browser's focus update.
                    await asyncio.sleep(1)
                    title = f"workspace-{width}"
                    await page.keyboard.type(f"data:text/html,<title>{title}</title><h1>Browser ready</h1>", delay=30)
                    await page.keyboard.press("Enter")
                    async with asyncio.timeout(30):
                        while True:
                            targets = await page.request.get("http://127.0.0.1:8080/cdp/json/list")
                            if any(target.get("title") == title for target in await targets.json()):
                                break
                            await asyncio.sleep(0.25)
                except Exception:
                    await page.screenshot(path=str(output / f"browser-failed-{width}.png"))
                    print(f"Browser errors: {errors}")
                    print(await frame.locator("body").inner_text())
                    targets = await page.request.get("http://127.0.0.1:8080/cdp/json/list")
                    print(await targets.json())
                    raise
                assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                await page.screenshot(path=str(output / f"browser-{width}.png"))
                await page.get_by_role("tab", name="Terminal").click()
                terminal_element = await page.query_selector("#terminal")
                terminal = await terminal_element.content_frame()
                await terminal.wait_for_function("document.body.textContent.includes('Terminal ready')")
                await terminal.locator(".xterm-helper-textarea").focus()
                await page.keyboard.type("printf 'ui-%s-ok\\n' terminal")
                await page.keyboard.press("Enter")
                await terminal.wait_for_function("document.body.textContent.includes('ui-terminal-ok')")
                await page.screenshot(path=str(output / f"terminal-{width}.png"))
                assert not errors, errors
                await page.close()
        finally:
            await browser.close()
    print("Desktop and mobile browser/terminal workspace checks passed")


if __name__ == "__main__":
    asyncio.run(main())
