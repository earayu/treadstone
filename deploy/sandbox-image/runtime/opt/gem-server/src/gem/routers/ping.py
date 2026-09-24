from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from ..utils import resolution


class Resolution(BaseModel):
    width: int = Field(..., gt=0, description="Screen width in pixels.")
    height: int = Field(..., gt=0, description="Screen height in pixels.")


class PingBody(BaseModel):
    """
    Represents the body of a ping request to the server.
    """

    resolution: Optional[Resolution] = Field(
        None, description="The desired screen resolution."
    )


# Create the router for the ping endpoint
router = APIRouter()


@router.post("/v1/ping", response_class=PlainTextResponse)
async def ping(body: Optional[PingBody] = None) -> str:
    """
    Ping the server to check if it is running.
    """
    try:
        if body and body.resolution is not None:
            resolution.set_resolution(
                width=body.resolution.width,
                height=body.resolution.height,
            )
        return "pong"
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )
