from pydantic import BaseModel, Field
from typing import Optional
import uuid


class ShellExecRequest(BaseModel):
    """Shell command execution request model"""

    id: Optional[str] = Field(
        None,
        description='Unique identifier of the target shell session, if not provided, one will be automatically created',
    )
    exec_dir: Optional[str] = Field(
        None,
        description='Working directory for command execution (must use absolute path)',
    )
    command: str = Field(..., description='Shell command to execute')
    async_mode: bool = Field(
        False,
        description='Whether to execute command asynchronously (default: False for async, False for synchronous execution)',
    )
    timeout: Optional[float] = Field(
        None,
        description='Maximum time (seconds) to wait for command completion before returning running status',
    )


class ShellViewRequest(BaseModel):
    """Shell session content view request model"""

    id: str = Field(..., description='Unique identifier of the target shell session')


class ShellWaitRequest(BaseModel):
    """Shell process wait request model"""

    id: str = Field(..., description='Unique identifier of the target shell session')
    seconds: Optional[int] = Field(None, description='Wait time (seconds)')


class ShellWriteToProcessRequest(BaseModel):
    """Request model for writing input to a running process"""

    id: str = Field(..., description='Unique identifier of the target shell session')
    input: str = Field(..., description='Input content to write to the process')
    press_enter: bool = Field(..., description='Whether to press enter key after input')


class ShellKillProcessRequest(BaseModel):
    """Request model for terminating a running process"""

    id: str = Field(..., description='Unique identifier of the target shell session')


class ShellSessionStats(BaseModel):
    """Shell session statistics model"""

    total_sessions: int = Field(..., description='Total number of sessions')
    active_sessions: int = Field(
        ..., description='Number of active sessions (used within last 5 minutes)'
    )
    idle_sessions: int = Field(..., description='Number of idle sessions')
    max_sessions: int = Field(..., description='Maximum allowed sessions')
    session_timeout: int = Field(..., description='Session timeout in seconds')
    usage_ratio: float = Field(..., description='Session usage ratio (0.0 to 1.0)')


class ShellCreateSessionRequest(BaseModel):
    """Shell session creation request model"""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description='Unique identifier for the shell session, auto-generated if not provided',
    )
    exec_dir: Optional[str] = Field(
        None,
        description='Working directory for the new session (must use absolute path)',
    )


class ShellCreateSessionResponse(BaseModel):
    """Shell session creation response model"""

    session_id: str = Field(
        ..., description='Unique identifier of the created shell session'
    )
    working_dir: str = Field(
        ..., description='Working directory of the created session'
    )
