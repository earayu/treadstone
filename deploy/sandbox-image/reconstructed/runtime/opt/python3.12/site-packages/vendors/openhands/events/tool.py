from typing import Any, Dict
from pydantic import BaseModel


class ToolCallMetadata(BaseModel):
    # Metadata for tool/function calls
    function_name: str  # Name of the function that was called
    tool_call_id: str  # ID of the tool call

    # Replace ModelResponse with a generic dict
    model_response: Dict[str, Any]
    total_calls_in_response: int
