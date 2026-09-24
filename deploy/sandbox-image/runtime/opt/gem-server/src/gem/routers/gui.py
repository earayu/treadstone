import io
import os
import platform
from typing import Annotated, List, Literal, Optional, Set, Union

import pyautogui
import pyperclip
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.responses import StreamingResponse


VALID_KEYBOARD_KEYS_SET: Set[str] = {
    "\t",
    "\n",
    "\r",
    " ",
    "!",
    '"',
    "#",
    "$",
    "%",
    "&",
    "'",
    "(",
    ")",
    "*",
    "+",
    ",",
    "-",
    ".",
    "/",
    "0",
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    ":",
    ";",
    "<",
    "=",
    ">",
    "?",
    "@",
    "[",
    "\\",
    "]",
    "^",
    "_",
    "`",
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
    "{",
    "|",
    "}",
    "~",
    "accept",
    "add",
    "alt",
    "altleft",
    "altright",
    "apps",
    "backspace",
    "browserback",
    "browserfavorites",
    "browserforward",
    "browserhome",
    "browserrefresh",
    "browsersearch",
    "browserstop",
    "capslock",
    "clear",
    "convert",
    "ctrl",
    "ctrlleft",
    "ctrlright",
    "decimal",
    "del",
    "delete",
    "divide",
    "down",
    "end",
    "enter",
    "esc",
    "escape",
    "execute",
    "f1",
    "f10",
    "f11",
    "f12",
    "f13",
    "f14",
    "f15",
    "f16",
    "f17",
    "f18",
    "f19",
    "f2",
    "f20",
    "f21",
    "f22",
    "f23",
    "f24",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "final",
    "fn",
    "hanguel",
    "hangul",
    "hanja",
    "help",
    "home",
    "insert",
    "junja",
    "kana",
    "kanji",
    "launchapp1",
    "launchapp2",
    "launchmail",
    "launchmediaselect",
    "left",
    "modechange",
    "multiply",
    "nexttrack",
    "nonconvert",
    "num0",
    "num1",
    "num2",
    "num3",
    "num4",
    "num5",
    "num6",
    "num7",
    "num8",
    "num9",
    "numlock",
    "pagedown",
    "pageup",
    "pause",
    "pgdn",
    "pgup",
    "playpause",
    "prevtrack",
    "print",
    "printscreen",
    "prntscrn",
    "prtsc",
    "prtscr",
    "return",
    "right",
    "scrolllock",
    "select",
    "separator",
    "shift",
    "shiftleft",
    "shiftright",
    "sleep",
    "stop",
    "subtract",
    "tab",
    "up",
    "volumedown",
    "volumemute",
    "volumeup",
    "win",
    "winleft",
    "winright",
    "yen",
    "command",
    "option",
    "optionleft",
    "optionright",
}


class BaseAction(BaseModel):
    action_type: str


class CoordinateAction(BaseAction):
    x: Optional[float] = None
    y: Optional[float] = None

    @model_validator(mode="after")
    def validate_coordinates(self) -> "CoordinateAction":
        max_x, max_y = pyautogui.size()
        if self.x is not None and not (0 <= self.x <= max_x):
            raise ValueError(f"x coordinate must be between 0 and {max_x}")
        if self.y is not None and not (0 <= self.y <= max_y):
            raise ValueError(f"y coordinate must be between 0 and {max_y}")
        return self


class SingleKeyAction(BaseAction):
    key: str

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        if v not in VALID_KEYBOARD_KEYS_SET:
            raise ValueError(f"Invalid keyboard key: '{v}'. It is not a valid key.")
        return v


class MoveToAction(CoordinateAction):
    action_type: Literal["MOVE_TO"] = "MOVE_TO"
    x: float = Field(description="Target x-coordinate")
    y: float = Field(description="Target y-coordinate")


class MoveRelAction(BaseAction):
    action_type: Literal["MOVE_REL"] = "MOVE_REL"
    x_offset: float = Field(description="Relative current position x-axis movement")
    y_offset: float = Field(description="Relative current position y-axis movement")


class ClickAction(CoordinateAction):
    action_type: Literal["CLICK"] = "CLICK"
    button: Literal["left", "right", "middle"] = "left"
    num_clicks: Literal[1, 2, 3] = 1


class MouseDownAction(BaseAction):
    action_type: Literal["MOUSE_DOWN"] = "MOUSE_DOWN"
    button: Literal["left", "right", "middle"] = "left"


class MouseUpAction(BaseAction):
    action_type: Literal["MOUSE_UP"] = "MOUSE_UP"
    button: Literal["left", "right", "middle"] = "left"


class RightClickAction(CoordinateAction):
    action_type: Literal["RIGHT_CLICK"] = "RIGHT_CLICK"


class DoubleClickAction(CoordinateAction):
    action_type: Literal["DOUBLE_CLICK"] = "DOUBLE_CLICK"


class DragToAction(CoordinateAction):
    action_type: Literal["DRAG_TO"] = "DRAG_TO"
    x: float = Field(description="Target x-coordinate for drag")
    y: float = Field(description="Target y-coordinate for drag")


class DragRelAction(BaseAction):
    action_type: Literal["DRAG_REL"] = "DRAG_REL"
    x_offset: float = Field(
        description="Relative current position x-axis drag movement"
    )
    y_offset: float = Field(
        description="Relative current position y-axis drag movement"
    )


class ScrollAction(BaseAction):
    action_type: Literal["SCROLL"] = "SCROLL"
    dx: int = 0
    dy: int = 0

    @model_validator(mode="after")
    def check_at_least_one_scroll(self) -> "ScrollAction":
        if self.dx == 0 and self.dy == 0:
            raise ValueError("At least one of 'dx' or 'dy' must be non-zero")
        return self


class TypingAction(BaseAction):
    action_type: Literal["TYPING"] = "TYPING"
    text: str = Field(min_length=1)
    use_clipboard: Optional[bool] = Field(
        default=True,
        description="Use clipboard for better character support (recommended for special/ASCII characters)",
    )


class PressAction(SingleKeyAction):
    action_type: Literal["PRESS"] = "PRESS"


class KeyDownAction(SingleKeyAction):
    action_type: Literal["KEY_DOWN"] = "KEY_DOWN"


class KeyUpAction(SingleKeyAction):
    action_type: Literal["KEY_UP"] = "KEY_UP"


class HotkeyAction(BaseAction):
    action_type: Literal["HOTKEY"] = "HOTKEY"
    keys: List[str] = Field(min_length=1)

    @field_validator("keys")
    @classmethod
    def validate_keys(cls, v: List[str]) -> List[str]:
        for key in v:
            if key not in VALID_KEYBOARD_KEYS_SET:
                raise ValueError(f"Invalid keyboard key in list: '{key}'.")
        return v


class WaitAction(BaseAction):
    action_type: Literal["WAIT"] = "WAIT"
    duration: float = Field(gt=0, description="Duration to wait in seconds")


AnyAction = Union[
    MoveToAction,
    MoveRelAction,
    ClickAction,
    MouseDownAction,
    MouseUpAction,
    RightClickAction,
    DoubleClickAction,
    DragToAction,
    DragRelAction,
    ScrollAction,
    TypingAction,
    PressAction,
    KeyDownAction,
    KeyUpAction,
    HotkeyAction,
    WaitAction,
]


class ActionResponse(BaseModel):
    status: Literal["success"]
    action_performed: str


router = APIRouter()


@router.get(
    "/screenshot",
    operation_id="take_screenshot",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Screenshot image",
            "content": {"image/png": {}},
            "headers": {
                "x-screen-width": {
                    "description": "Screen width",
                    "schema": {"type": "string"},
                },
                "x-screen-height": {
                    "description": "Screen height",
                    "schema": {"type": "string"},
                },
                "x-image-width": {
                    "description": "Image width",
                    "schema": {"type": "string"},
                },
                "x-image-height": {
                    "description": "Image height",
                    "schema": {"type": "string"},
                },
            },
        }
    },
)
async def take_screenshot():
    """Take a screenshot of the current display.

    Returns:
        StreamingResponse: PNG image data with proper headers including display and screenshot dimensions
    """
    display_width, display_height = pyautogui.size()

    img = pyautogui.screenshot()

    screenshot_width, screenshot_height = img.size

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="image/png",
        headers={
            "x-screen-width": str(display_width),
            "x-screen-height": str(display_height),
            "x-image-width": str(screenshot_width),
            "x-image-height": str(screenshot_height),
        },
    )


@router.post("/actions", operation_id="execute_action", response_model=ActionResponse)
async def execute_action(
    action: Annotated[AnyAction, Field(discriminator="action_type")],
) -> ActionResponse:
    """Execute a validated action on the current display."""
    try:
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
                is_macos = platform.system() == "Darwin"
                if is_macos:
                    # https://github.com/asweigart/pyautogui/issues/796#issuecomment-2052361304
                    pyautogui.keyUp("fn")
                    pyautogui.sleep(0.1)

                pyautogui.hotkey(
                    "command" if platform.system() == "Darwin" else "ctrl",
                    "v",
                )
                pyautogui.sleep(0.1)
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

        return ActionResponse(status="success", action_performed=action.action_type)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error during action execution: {e}"
        )
