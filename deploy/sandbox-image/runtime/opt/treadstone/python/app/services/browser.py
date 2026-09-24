from importlib import resources
import logging
import os
import platform
import subprocess
from typing import TYPE_CHECKING, Annotated
from urllib.parse import urlparse

from fastapi import Request


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

    # Move pyautogui to TYPE_CHECKING to avoid slow import

import httpx
import pyperclip
from pydantic import Field

from app.models.browser import (
    ActionResponse,
    AnyAction,
    BrowserInfoResult,
    BrowserScreenshotResult,
    BrowserViewport,
    ClickAction,
    DoubleClickAction,
    DragRelAction,
    DragToAction,
    HotkeyAction,
    KeyDownAction,
    KeyUpAction,
    MouseDownAction,
    MouseUpAction,
    MoveRelAction,
    MoveToAction,
    PressAction,
    RightClickAction,
    ScrollAction,
    TypingAction,
    WaitAction,
)

class XrandrError(Exception):
    """Custom exception for xrandr related errors."""

    pass


class BrowserService:
    """Browser Operation Service"""

    def __init__(self):
        self.gem_srv_port = os.environ.get('GEM_BROWSER_SRV_PORT', 8088)

    def _rewrite_websocket_urls(
        self, url: str, proxy_host: str, ws_protocol: str, path_prefix: str = ''
    ) -> str:
        """
        Rewrite WebSocket URLs in CDP JSON response.

        Args:
            url: Original WebSocket URL
            proxy_host: Proxy host (e.g., 'example.com:8080')
            ws_protocol: WebSocket protocol ('ws' or 'wss')
            path_prefix: Path prefix from X-Forwarded-Prefix header (e.g., '/api/v1')

        Returns:
            Rewritten WebSocket URL with path prefix if provided

        Notes:
            - If path_part already contains the path_prefix, we don't add it again
            - This handles cases where upstream proxy has already rewritten paths
        """

        path_part = urlparse(url).path

        # Check if path_part already starts with path_prefix to avoid duplication
        # This happens when upstream proxy has already rewritten the path
        if path_prefix and path_part.startswith(path_prefix):
            # Path already contains prefix, just add /cdp after the prefix
            # Extract the part after prefix
            remaining_path = path_part[len(path_prefix):]
            new_url = f'{ws_protocol}://{proxy_host}{path_prefix}/cdp{remaining_path}'
        else:
            # Normal case: add prefix and /cdp
            new_url = f'{ws_protocol}://{proxy_host}{path_prefix}/cdp{path_part}'

        logging.info(f'Rewriting WebSocket URL: {url} -> {new_url}')

        return new_url

    async def get_browser_info(self, request: Request):
        from app.utils import normalize_path_prefix

        async with httpx.AsyncClient(timeout=15) as client:
            headers = {
                key: value
                for key, value in request.headers.items()
                if key.lower() not in ('host', 'accept-encoding', 'content-length')
            }
            headers['Host'] = f'127.0.0.1:{self.gem_srv_port}'

            logger.info(f'Headers: {headers}')

            response = await client.get(
                f'http://127.0.0.1:{self.gem_srv_port}/json/version', headers=headers
            )
            res = response.json()

            proxy_host = request.headers.get('host', request.url.netloc)
            logger.info('proxy_host: %s', proxy_host)

            # Check X-Forwarded-Proto first, fallback to request.url.scheme
            # In reverse proxy scenarios, the internal request may be http
            # but the external client connection is https
            forwarded_proto = request.headers.get('x-forwarded-proto', '').lower()
            if forwarded_proto in ('https', 'http'):
                is_https = forwarded_proto == 'https'
            else:
                is_https = request.url.scheme == 'https'

            http_scheme = 'https' if is_https else 'http'
            ws_protocol = 'wss' if is_https else 'ws'

            logger.info('Protocol detection - X-Forwarded-Proto: %s, request.url.scheme: %s, final: %s',
                       forwarded_proto or 'none', request.url.scheme, http_scheme)

            # Get and normalize path prefix from X-Forwarded-Prefix header
            path_prefix = normalize_path_prefix(
                request.headers.get('x-forwarded-prefix')
            )

            cdp_url = self._rewrite_websocket_urls(
                res.get('webSocketDebuggerUrl'), proxy_host, ws_protocol, path_prefix
            )
            vnc_url = f'{http_scheme}://{proxy_host}{path_prefix}/vnc/index.html'

            viewport = self.get_resolution()
            logger.info('viewport: %s', viewport)

            width = viewport.width if viewport else os.environ.get('DISPLAY_WIDTH', 0)
            height = viewport.height if viewport else os.environ.get('DISPLAY_HEIGHT', 0)
            return BrowserInfoResult(
                user_agent=res.get('User-Agent', ''),
                cdp_url=cdp_url,
                vnc_url=vnc_url,
                viewport=BrowserViewport(
                    width=int(width),
                    height=int(height),
                ),
            )

    async def task_screenshot(self) -> tuple['PILImage', BrowserScreenshotResult]:
        import pyautogui  # Lazy import to avoid startup delay

        display_width, display_height = pyautogui.size()

        image = pyautogui.screenshot()

        screenshot_width, screenshot_height = image.size

        return image, BrowserScreenshotResult(
            display_width=display_width,
            display_height=display_height,
            screenshot_width=screenshot_width,
            screenshot_height=screenshot_height,
        )

    async def execute_action(
        self, action: Annotated[AnyAction, Field(discriminator='action_type')]
    ) -> ActionResponse:
        import pyautogui  # Lazy import to avoid startup delay

        if isinstance(action, MoveToAction):
            pyautogui.moveTo(action.x, action.y)
        elif isinstance(action, MoveRelAction):
            pyautogui.moveRel(action.x_offset, action.y_offset)
        elif isinstance(action, ClickAction):
            pyautogui.click(
                x=action.x, y=action.y, button=action.button, clicks=action.num_clicks
            )
        elif isinstance(action, MouseDownAction):
            pyautogui.mouseDown(button=action.button)
        elif isinstance(action, MouseUpAction):
            pyautogui.mouseUp(button=action.button)
        elif isinstance(action, RightClickAction):
            pyautogui.rightClick(x=action.x, y=action.y)
        elif isinstance(action, DoubleClickAction):
            pyautogui.doubleClick(x=action.x, y=action.y)
        elif isinstance(action, DragToAction):
            pyautogui.dragTo(action.x, action.y)
        elif isinstance(action, DragRelAction):
            pyautogui.dragRel(action.x_offset, action.y_offset)
        elif isinstance(action, ScrollAction):
            pyautogui.scroll(action.dy)
            pyautogui.hscroll(action.dx)
        elif isinstance(action, TypingAction):
            if action.use_clipboard:
                try:
                    original_clipboard = pyperclip.paste()
                except:
                    original_clipboard = None
                pyperclip.copy(action.text)
                is_macos = platform.system() == 'Darwin'
                if is_macos:
                    # https://github.com/asweigart/pyautogui/issues/796#issuecomment-2052361304
                    pyautogui.keyUp('fn')
                    pyautogui.sleep(0.1)

                pyautogui.hotkey(
                    'command' if platform.system() == 'Darwin' else 'ctrl',
                    'v',
                )
                pyautogui.sleep(0.1)
                if original_clipboard is not None:
                    pyperclip.copy(original_clipboard)
            else:
                pyautogui.typewrite(action.text)
        elif isinstance(action, PressAction):
            pyautogui.press(action.key)
        elif isinstance(action, KeyDownAction):
            pyautogui.keyDown(action.key)
        elif isinstance(action, KeyUpAction):
            pyautogui.keyUp(action.key)
        elif isinstance(action, HotkeyAction):
            pyautogui.hotkey(*action.keys)
        elif isinstance(action, WaitAction):
            pyautogui.sleep(action.duration)

        return ActionResponse(status='success', action_performed=action.action_type)


    @staticmethod
    def _generate_exact_modeline(
        width: int, height: int, refresh_rate: float = 60.0
    ) -> tuple[str, str]:
        """
        Generates a precise xrandr modeline for a given resolution and refresh rate.

        Returns:
            A tuple containing (mode_name, modeline_params_string).
            The mode_name is in the standard "WIDTHxHEIGHT" format.
        """
        # The mode name should be the standard format to match system-defined modes.
        mode_name = f"{width}x{height}"

        # 1. Define simplified timing parameters
        h_sync_start = width + 16
        h_sync_end = h_sync_start + 96
        h_total = h_sync_end + 48

        v_sync_start = height + 3
        v_sync_end = v_sync_start + 5
        v_total = v_sync_end + 20

        # 2. Calculate the required pixel clock in MHz
        pclk_hz = h_total * v_total * refresh_rate
        pclk_mhz = pclk_hz / 1_000_000

        # 3. Format the modeline parameters into a single string
        modeline_params = (
            f"{pclk_mhz:.2f} "
            f"{width} {h_sync_start} {h_sync_end} {h_total} "
            f"{height} {v_sync_start} {v_sync_end} {v_total} "
            "+hsync +vsync"
        )

        return mode_name, modeline_params

    def get_resolution(self) -> BrowserViewport | None:
        command_pipeline = r'xrandr --verbose | grep -oP "(?<=current )\d+ x \d+"'

        try:
            # Step 1: Execute the entire pipeline using shell=True
            # shell=True tells Python to pass the command to the system's shell (/bin/sh or /bin/bash)
            # The shell understands the pipe '|' symbol and handles the connection.
            result = subprocess.run(
                command_pipeline,
                shell=True,
                capture_output=True,
                text=True,
                check=True
            )

            # The output of the whole pipeline is in result.stdout
            resolution_str = result.stdout.strip()

            if not resolution_str:
                print("Error: The command pipeline produced no output.")
                return None

            # Step 2: Parse the final output string
            parts = resolution_str.split(' x ')
            width = int(parts[0])
            height = int(parts[1])

            return BrowserViewport(width=width, height=height)

        except FileNotFoundError:
            print("Error: A command in the pipeline was not found (e.g., xrandr or grep).")
            return None
        except subprocess.CalledProcessError as e:
            print(f"Error during command execution: {e}")
            print(f"Stderr: {e.stderr}")
            return None

    def set_resolution(self, width: int, height: int) -> str:
        """
        Calculates a precise 60Hz modeline and calls the set-resolution.sh script
        to apply it. It uses a standard "WIDTHxHEIGHT" mode name for compatibility.

        Args:
            width: The target width.
            height: The target height.

        Returns:
            A success message extracted from the script's output.

        Raises:
            XrandrError: If the script fails or is not found.
        """
        try:
            mode_name, modeline_params = BrowserService._generate_exact_modeline(width, height)
            logger.info(
                f"Using standard mode name '{mode_name}' with "
                f"calculated modeline: {modeline_params}"
            )

            with resources.path("app.scripts", "set-resolution.sh") as script_path:
                command = [str(script_path), mode_name, modeline_params]
                logger.info(f"Executing command: {' '.join(command)}")

                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=True,
                    encoding="utf-8",
                )

            success_message = ""
            for line in result.stdout.strip().split("\n"):
                if line.startswith("Success:"):
                    success_message = line.replace("Success: ", "")

            if not success_message:
                success_message = (
                    "Resolution script executed successfully, but no success message found."
                )

            logger.info(f"Script output: {result.stdout.strip()}")
            return success_message

        except FileNotFoundError as e:
            raise XrandrError(f"Script 'set-resolution.sh' not found. Original error: {e}")
        except subprocess.CalledProcessError as e:
            error_output = e.stderr.strip()
            logging.error(
                f"Script failed with exit code {e.returncode}. Stderr: {error_output}"
            )
            raise XrandrError(f"Failed to set resolution. Reason: {error_output}")
