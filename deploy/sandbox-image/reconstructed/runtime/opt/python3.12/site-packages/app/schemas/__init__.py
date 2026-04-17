from enum import Enum


class ResponseFormat(str, Enum):
    """Response format options"""

    DETAILED = "detailed"
    CONCISE = "concise"
