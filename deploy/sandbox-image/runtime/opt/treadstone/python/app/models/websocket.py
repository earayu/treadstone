"""
WebSocket message models for shell terminal
"""

from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class WebSocketMessage(BaseModel):
    """Base WebSocket message model"""

    type: str = Field(..., description='Message type')
    data: Any = Field(None, description='Message data')


class WebSocketInputMessage(BaseModel):
    """WebSocket input message model"""

    type: str = Field(default='input', description='Message type')
    data: str = Field(..., description='Input data to send to terminal')


class WebSocketResizeMessage(BaseModel):
    """WebSocket resize message model"""

    type: str = Field(default='resize', description='Message type')
    data: Dict[str, int] = Field(
        ..., description='Terminal size data with cols and rows'
    )


class WebSocketOutputMessage(BaseModel):
    """WebSocket output message model"""

    type: str = Field(default='output', description='Message type')
    data: str = Field(..., description='Output data from terminal')


class WebSocketSessionMessage(BaseModel):
    """WebSocket session ID message model"""

    type: str = Field(default='session_id', description='Message type')
    data: str = Field(..., description='Session ID')


class WebSocketReadyMessage(BaseModel):
    """WebSocket ready message model"""

    type: str = Field(default='ready', description='Message type')
    data: str = Field(..., description='Ready message')


class WebSocketErrorMessage(BaseModel):
    """WebSocket error message model"""

    type: str = Field(default='error', description='Message type')
    data: str = Field(..., description='Error message')


class WebSocketProcessExitMessage(BaseModel):
    """WebSocket process exit message model"""

    type: str = Field(default='process_exit', description='Message type')
    code: int = Field(..., description='Exit code')


class WebSocketPingMessage(BaseModel):
    """WebSocket ping message model for heartbeat"""

    type: str = Field(default='ping', description='Message type')
    timestamp: Optional[int] = Field(None, description='Timestamp of ping message')


class WebSocketPongMessage(BaseModel):
    """WebSocket pong message model for heartbeat response"""

    type: str = Field(default='pong', description='Message type')
    timestamp: Optional[int] = Field(
        None, description='Timestamp from original ping message'
    )
