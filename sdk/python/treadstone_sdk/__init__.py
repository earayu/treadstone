"""A client library for accessing treadstone"""

from .client import AuthenticatedClient, Client

TREADSTONE_API_URL = "https://api.treadstone-ai.dev"

__all__ = (
    "AuthenticatedClient",
    "Client",
    "TREADSTONE_API_URL",
)
