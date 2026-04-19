"""
Jupyter service model definitions
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class KernelStatus(str, Enum):
    """Kernel execution status"""
    OK = 'ok'
    ERROR = 'error'
    TIMEOUT = 'timeout'
    UNKNOWN = 'unknown'


class OutputType(str, Enum):
    """Jupyter output types"""
    STREAM = 'stream'
    EXECUTE_RESULT = 'execute_result'
    DISPLAY_DATA = 'display_data'
    ERROR = 'error'


class JupyterOutput(BaseModel):
    """Single Jupyter output entry"""
    output_type: OutputType = Field(..., description='Type of output')
    name: Optional[str] = Field(None, description='Stream name (stdout/stderr)')
    text: Optional[str] = Field(None, description='Text output for stream')
    data: Optional[Dict[str, Any]] = Field(None, description='Data for execute_result/display_data')
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description='Output metadata')
    execution_count: Optional[int] = Field(None, description='Execution count for execute_result')
    ename: Optional[str] = Field(None, description='Error name')
    evalue: Optional[str] = Field(None, description='Error value')
    traceback: Optional[List[str]] = Field(None, description='Error traceback')


class ExecuteCodeResult(BaseModel):
    """Code execution result model"""
    kernel_name: str = Field(..., description='Kernel name used for execution')
    session_id: str = Field(..., description='Jupyter kernel session ID')
    status: KernelStatus = Field(..., description='Execution status')
    outputs: List[JupyterOutput] = Field(default_factory=list, description='Execution outputs')
    code: str = Field(..., description='Executed code')
    msg_id: Optional[str] = Field(None, description='Jupyter message ID')
    execution_count: Optional[int] = Field(None, description='Cell execution count')


class KernelInfo(BaseModel):
    """Kernel information model"""
    kernel_name: str = Field(..., description='Kernel name')
    available: bool = Field(..., description='Whether kernel is available')


class SessionInfo(BaseModel):
    """Active session information"""
    kernel_name: str = Field(..., description='Kernel name')
    last_used: float = Field(..., description='Last used timestamp')
    age_seconds: int = Field(..., description='Age of session in seconds')


class ActiveSessionsResult(BaseModel):
    """Active sessions result"""
    sessions: Dict[str, SessionInfo] = Field(..., description='Map of session ID to session info')
