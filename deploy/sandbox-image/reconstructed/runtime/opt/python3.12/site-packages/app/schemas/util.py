"""
Util request models
"""

from __future__ import annotations
from pydantic import BaseModel, Field


class UtilConvertToMarkdownRequest(BaseModel):
    """convert to markdown request"""

    uri: str = Field(..., description='The URI of the resource to convert')
