"""
Browser operation related models
"""

from typing import List, Literal, Optional, Set, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class BrowserViewport(BaseModel):
    width: int = Field(..., description='Viewport width')
    height: int = Field(..., description='Viewport height')


class BrowserInfoResult(BaseModel):
    """Browser Info result"""

    user_agent: str = Field(..., description='User agent')
    cdp_url: str = Field(..., description='Browser CDP URL')
    vnc_url: str = Field(..., description='VNC URL')
    viewport: BrowserViewport = Field(..., description='Viewport size')


class BrowserScreenshotResult(BaseModel):
    """Browser Screenshot result"""

    display_width: int = Field(..., description='Display width')
    display_height: int = Field(..., description='Display height')
    screenshot_width: int = Field(..., description='Screenshot width')
    screenshot_height: int = Field(..., description='Screenshot height')


VALID_KEYBOARD_KEYS_SET: Set[str] = {
    '\t',
    '\n',
    '\r',
    ' ',
    '!',
    '"',
    '#',
    '$',
    '%',
    '&',
    "'",
    '(',
    ')',
    '*',
    '+',
    ',',
    '-',
    '.',
    '/',
    '0',
    '1',
    '2',
    '3',
    '4',
    '5',
    '6',
    '7',
    '8',
    '9',
    ':',
    ';',
    '<',
    '=',
    '>',
    '?',
    '@',
    '[',
    '\\',
    ']',
    '^',
    '_',
    '`',
    'a',
    'b',
    'c',
    'd',
    'e',
    'f',
    'g',
    'h',
    'i',
    'j',
    'k',
    'l',
    'm',
    'n',
    'o',
    'p',
    'q',
    'r',
    's',
    't',
    'u',
    'v',
    'w',
    'x',
    'y',
    'z',
    '{',
    '|',
    '}',
    '~',
    'accept',
    'add',
    'alt',
    'altleft',
    'altright',
    'apps',
    'backspace',
    'browserback',
    'browserfavorites',
    'browserforward',
    'browserhome',
    'browserrefresh',
    'browsersearch',
    'browserstop',
    'capslock',
    'clear',
    'convert',
    'ctrl',
    'ctrlleft',
    'ctrlright',
    'decimal',
    'del',
    'delete',
    'divide',
    'down',
    'end',
    'enter',
    'esc',
    'escape',
    'execute',
    'f1',
    'f10',
    'f11',
    'f12',
    'f13',
    'f14',
    'f15',
    'f16',
    'f17',
    'f18',
    'f19',
    'f2',
    'f20',
    'f21',
    'f22',
    'f23',
    'f24',
    'f3',
    'f4',
    'f5',
    'f6',
    'f7',
    'f8',
    'f9',
    'final',
    'fn',
    'hanguel',
    'hangul',
    'hanja',
    'help',
    'home',
    'insert',
    'junja',
    'kana',
    'kanji',
    'launchapp1',
    'launchapp2',
    'launchmail',
    'launchmediaselect',
    'left',
    'modechange',
    'multiply',
    'nexttrack',
    'nonconvert',
    'num0',
    'num1',
    'num2',
    'num3',
    'num4',
    'num5',
    'num6',
    'num7',
    'num8',
    'num9',
    'numlock',
    'pagedown',
    'pageup',
    'pause',
    'pgdn',
    'pgup',
    'playpause',
    'prevtrack',
    'print',
    'printscreen',
    'prntscrn',
    'prtsc',
    'prtscr',
    'return',
    'right',
    'scrolllock',
    'select',
    'separator',
    'shift',
    'shiftleft',
    'shiftright',
    'sleep',
    'stop',
    'subtract',
    'tab',
    'up',
    'volumedown',
    'volumemute',
    'volumeup',
    'win',
    'winleft',
    'winright',
    'yen',
    'command',
    'option',
    'optionleft',
    'optionright',
}


class BaseAction(BaseModel):
    action_type: str


class CoordinateAction(BaseAction):
    x: Optional[float] = None
    y: Optional[float] = None

    @model_validator(mode='after')
    def validate_coordinates(self) -> 'CoordinateAction':
        import pyautogui

        max_x, max_y = pyautogui.size()
        if self.x is not None and not (0 <= self.x <= max_x):
            raise ValueError(f'x coordinate must be between 0 and {max_x}')
        if self.y is not None and not (0 <= self.y <= max_y):
            raise ValueError(f'y coordinate must be between 0 and {max_y}')
        return self


class SingleKeyAction(BaseAction):
    key: str

    @field_validator('key')
    @classmethod
    def validate_key(cls, v: str) -> str:
        if v not in VALID_KEYBOARD_KEYS_SET:
            raise ValueError(f"Invalid keyboard key: '{v}'. It is not a valid key.")
        return v


class MoveToAction(CoordinateAction):
    action_type: Literal['MOVE_TO'] = 'MOVE_TO'
    x: float = Field(description='Target x-coordinate')
    y: float = Field(description='Target y-coordinate')


class MoveRelAction(BaseAction):
    action_type: Literal['MOVE_REL'] = 'MOVE_REL'
    x_offset: float = Field(description='Relative current position x-axis movement')
    y_offset: float = Field(description='Relative current position y-axis movement')


class ClickAction(CoordinateAction):
    action_type: Literal['CLICK'] = 'CLICK'
    button: Literal['left', 'right', 'middle'] = 'left'
    num_clicks: Literal[1, 2, 3] = 1


class MouseDownAction(BaseAction):
    action_type: Literal['MOUSE_DOWN'] = 'MOUSE_DOWN'
    button: Literal['left', 'right', 'middle'] = 'left'


class MouseUpAction(BaseAction):
    action_type: Literal['MOUSE_UP'] = 'MOUSE_UP'
    button: Literal['left', 'right', 'middle'] = 'left'


class RightClickAction(CoordinateAction):
    action_type: Literal['RIGHT_CLICK'] = 'RIGHT_CLICK'


class DoubleClickAction(CoordinateAction):
    action_type: Literal['DOUBLE_CLICK'] = 'DOUBLE_CLICK'


class DragToAction(CoordinateAction):
    action_type: Literal['DRAG_TO'] = 'DRAG_TO'
    x: float = Field(description='Target x-coordinate for drag')
    y: float = Field(description='Target y-coordinate for drag')


class DragRelAction(BaseAction):
    action_type: Literal['DRAG_REL'] = 'DRAG_REL'
    x_offset: float = Field(
        description='Relative current position x-axis drag movement'
    )
    y_offset: float = Field(
        description='Relative current position y-axis drag movement'
    )


class ScrollAction(BaseAction):
    action_type: Literal['SCROLL'] = 'SCROLL'
    dx: int = 0
    dy: int = 0

    @model_validator(mode='after')
    def check_at_least_one_scroll(self) -> 'ScrollAction':
        if self.dx == 0 and self.dy == 0:
            raise ValueError("At least one of 'dx' or 'dy' must be non-zero")
        return self


class TypingAction(BaseAction):
    action_type: Literal['TYPING'] = 'TYPING'
    text: str = Field(min_length=1)
    use_clipboard: Optional[bool] = Field(
        default=True,
        description='Use clipboard for better character support (recommended for special/ASCII characters)',
    )


class PressAction(SingleKeyAction):
    action_type: Literal['PRESS'] = 'PRESS'


class KeyDownAction(SingleKeyAction):
    action_type: Literal['KEY_DOWN'] = 'KEY_DOWN'


class KeyUpAction(SingleKeyAction):
    action_type: Literal['KEY_UP'] = 'KEY_UP'


class HotkeyAction(BaseAction):
    action_type: Literal['HOTKEY'] = 'HOTKEY'
    keys: List[str] = Field(min_length=1)

    @field_validator('keys')
    @classmethod
    def validate_keys(cls, v: List[str]) -> List[str]:
        for key in v:
            if key not in VALID_KEYBOARD_KEYS_SET:
                raise ValueError(f"Invalid keyboard key in list: '{key}'.")
        return v


class WaitAction(BaseAction):
    action_type: Literal['WAIT'] = 'WAIT'
    duration: float = Field(gt=0, description='Duration to wait in seconds')


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
    status: Literal['success']
    action_performed: str
