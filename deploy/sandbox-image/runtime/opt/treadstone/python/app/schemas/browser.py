from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, model_validator

class Resolution(BaseModel):
    width: int = Field(..., gt=0, description="Screen width in pixels.")
    height: int = Field(..., gt=0, description="Screen height in pixels.")

ALLOWED_PAIRS = {
    (1280, 720),
    (1920, 1200),
    (1920, 1080),
    (1600, 1200),
    (1680, 1050),
    (1400, 1050),
    (1360, 768),
    (1280, 1024),
    (1280, 960),
    (1280, 800),
    (1024, 768),
    (800, 600),
    (640, 480)
}

allowed_resolutions_str = ", ".join([f"{w}x{h}" for w, h in ALLOWED_PAIRS])

class BrowserConfigRequest(BaseModel):
    """Browser configuration request"""

    resolution: Optional[Resolution] = Field(
        None, description=f"The desired screen resolution, allowed values are: {allowed_resolutions_str}."
    )

    @model_validator(mode='after')
    def check_allowed_resolution_pair(self) -> 'Resolution':
        if self.resolution is not None and self.resolution.width and self.resolution.height:
            width = self.resolution.width
            height = self.resolution.height
            if (width, height) not in ALLOWED_PAIRS:
                allowed_resolutions_str = ", ".join([f"{w}x{h}" for w, h in ALLOWED_PAIRS])
                raise ValueError(
                    f"not supported: {width}x{height}。 "
                    f"allowed values are: {allowed_resolutions_str}"
                )

        return self
