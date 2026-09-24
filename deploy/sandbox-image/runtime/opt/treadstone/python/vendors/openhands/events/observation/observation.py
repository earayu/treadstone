from dataclasses import dataclass

from vendors.openhands.events.event import Event


@dataclass
class Observation(Event):
    """Base class for observations from the environment.

    Attributes:
        content: The content of the observation. For large observations,
                this might be truncated when stored.
    """

    content: str
