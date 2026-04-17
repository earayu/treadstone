import base64
import binascii
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional, cast
from urllib.parse import parse_qs, urlparse

from cachelib import SimpleCache
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from jwt import ExpiredSignatureError, PyJWTError, decode


# --- 1. Configuration Class ---


class AuthConfig:
    """
    Encapsulates all configuration logic for the authentication service.

    It reads settings from environment variables upon initialization, providing
    a single source of truth for configuration values.
    """

    def __init__(
        self,
        jwt_public_key_env: str = "JWT_PUBLIC_KEY",
        ticket_ttl_env: str = "TICKET_TTL_SECONDS",
        jwt_algorithms: Optional[list[str]] = None,
        default_ticket_ttl: int = 30,
        default_cache_ttl: int = 1800,
    ):
        """
        Initializes the authentication configuration.

        Args:
            jwt_public_key_env: The name of the environment variable for the JWT public key.
            ticket_ttl_env: The name of the environment variable for the ticket TTL in seconds.
            jwt_algorithms: Supported JWT algorithms. Defaults to ["RS256"].
            default_ticket_ttl: Default ticket TTL in seconds.
            default_cache_ttl: Default cache TTL for tokens without expiration.
        """
        self.jwt_algorithms: list[str] = jwt_algorithms or ["RS256"]
        self.default_ticket_ttl: int = default_ticket_ttl
        self.default_cache_ttl: int = default_cache_ttl

        self.jwt_public_key: Optional[str] = self._load_jwt_public_key(
            jwt_public_key_env
        )
        self.ticket_ttl: int = self._load_ticket_ttl(ticket_ttl_env)

    def _load_jwt_public_key(self, env_var: str) -> Optional[str]:
        """Loads and decodes the JWT public key from an environment variable."""
        b64_encoded_key = os.environ.get(env_var)
        if not b64_encoded_key:
            logging.warning(
                f"Environment variable '{env_var}' is not set. "
                "JWT validation will be disabled."
            )
            return None

        try:
            decoded_key = base64.b64decode(b64_encoded_key).decode("utf-8")
            logging.info(f"Successfully decoded JWT public key from '{env_var}'.")
            return decoded_key
        except (binascii.Error, UnicodeDecodeError) as e:
            logging.error(
                f"Failed to decode JWT public key from '{env_var}': {e}. "
                "Service will be unable to validate JWTs."
            )
            return None

    def _load_ticket_ttl(self, env_var: str) -> int:
        """Loads the ticket TTL from an environment variable with validation."""
        raw_value = os.environ.get(env_var)
        if raw_value is None:
            return self.default_ticket_ttl

        try:
            parsed_ttl = int(raw_value)
            if parsed_ttl >= 0:
                logging.info(
                    f"Ticket TTL is set to {parsed_ttl} seconds from '{env_var}'."
                )
                return parsed_ttl
            else:
                logging.warning(
                    f"Value for '{env_var}' cannot be negative ('{raw_value}'). "
                    f"Falling back to default of {self.default_ticket_ttl} seconds."
                )
        except ValueError:
            logging.warning(
                f"Invalid value for '{env_var}' ('{raw_value}'). It must be an integer. "
                f"Falling back to default of {self.default_ticket_ttl} seconds."
            )

        return self.default_ticket_ttl


# --- 2. Service Class ---


class AuthService:
    """
    Encapsulates all business logic for authentication.

    This service class contains the methods for creating tickets, validating tickets,
    and validating JWTs. It relies on an AuthConfig instance for its configuration
    and uses caches for performance.
    """

    def __init__(
        self,
        config: AuthConfig,
        jwt_cache: Optional[SimpleCache] = None,
        ticket_cache: Optional[SimpleCache] = None,
    ):
        """
        Initializes the authentication service.

        Args:
            config: An instance of AuthConfig.
            jwt_cache: A cache instance for storing validated JWTs. If None, creates a new one.
            ticket_cache: A cache instance for storing active tickets. If None, creates a new one.
        """
        self.config = config
        self.jwt_cache = jwt_cache or SimpleCache()
        self.ticket_cache = ticket_cache or SimpleCache()

    def create_ticket(self) -> Dict[str, Any]:
        """Creates a generic, short-lived ticket and stores it in the cache."""
        ticket = str(uuid.uuid4())
        self.ticket_cache.set(ticket, True, timeout=self.config.ticket_ttl)
        logging.info(
            f"Generated a new ticket with a {self.config.ticket_ttl}s TTL: {ticket}"
        )

        return {
            "ticket": ticket,
            "expires_in": self.config.ticket_ttl,
        }

    def validate_ticket(self, ticket: str) -> bool:
        """Validates if a ticket is still active."""
        return bool(self.ticket_cache.get(ticket))

    def parse_ticket_from_uri(self, original_uri: str) -> Optional[str]:
        """Extracts ticket parameter from URI query string."""
        parsed_uri = urlparse(original_uri)
        query_params = parse_qs(parsed_uri.query)
        ticket_list = query_params.get("ticket")
        return ticket_list[-1] if ticket_list else None

    def _validate_jwt(self, token: str) -> Dict[str, Any]:
        """Internal logic to validate a JWT token."""
        if not self.config.jwt_public_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication is not possible. JWT public key has not been configured.",
            )

        # Check cache first
        if self.jwt_cache.get(token):
            return {"status": "ok", "message": "Access granted from cache."}

        try:
            payload = decode(
                token, self.config.jwt_public_key, algorithms=self.config.jwt_algorithms
            )

            # Cache the token if it has a valid expiration claim ('exp').
            exp = payload.get("exp")
            if exp and isinstance(exp, int):
                ttl = exp - int(time.time())
                if ttl > 0:
                    self.jwt_cache.set(token, True, timeout=ttl)
            else:
                # For tokens without expiration, use default cache TTL
                self.jwt_cache.set(token, True, timeout=self.config.default_cache_ttl)

            return {"status": "ok", "message": "Access granted after validation."}

        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
            )
        except PyJWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}"
            )

    def authenticate_request(self, request: Request) -> Dict[str, str]:
        """
        Handles an authentication request, supporting both ticket and JWT methods.

        It prioritizes ticket validation if a 'ticket' query parameter is found.
        Otherwise, it falls back to standard JWT validation via the 'Authorization' header.
        """
        # --- Priority 1: Ticket Validation ---
        original_uri = request.headers.get("x-original-uri", "")
        ticket = self.parse_ticket_from_uri(original_uri)

        if ticket:
            if self.validate_ticket(ticket):
                logging.info(
                    f"Successfully validated ticket '{ticket}' from URI '{original_uri}'"
                )
                return {"status": "ok", "message": "Ticket validated."}
            else:
                logging.warning(
                    f"Invalid or expired ticket '{ticket}' received in URI: {original_uri}"
                )
                raise HTTPException(
                    status_code=401, detail="Invalid or expired ticket."
                )

        # --- Priority 2: JWT Validation ---
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header is missing",
            )

        try:
            token_type, token = auth_header.split(maxsplit=1)
            if token_type.lower() != "bearer":
                raise ValueError("Invalid token type")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format. Must be 'Bearer <token>'",
            )

        return self._validate_jwt(token)


# --- 3. Dependency Injection Setup ---


def get_auth_service(request: Request) -> AuthService:
    """Dependency provider for the AuthService."""
    if not hasattr(request.app.state, "auth_service"):
        raise HTTPException(
            status_code=503, detail="Authentication service is not available."
        )
    return cast(AuthService, request.app.state.auth_service)


# --- 4. API Router ---

router = APIRouter()


@router.post("/tickets", status_code=status.HTTP_200_OK, tags=["Authentication"])
async def create_ticket(
    service: AuthService = Depends(get_auth_service),
) -> Dict[str, Any]:
    """
    Creates and returns a generic, short-lived ticket.

    This is a non-idempotent action; each call creates a new, unique ticket.
    """
    return service.create_ticket()


@router.get("/auth", status_code=status.HTTP_200_OK, tags=["Authentication"])
async def authenticate_request(
    request: Request, service: AuthService = Depends(get_auth_service)
) -> Dict[str, str]:
    """
    Receives an authentication subrequest (e.g., from Nginx auth_request).

    It validates the request based on either a ticket in the 'x-original-uri'
    header or a JWT in the 'Authorization' header.
    """
    return service.authenticate_request(request)


# --- 5. Lifecycle Management ---


async def startup(app: FastAPI) -> None:
    """Initializes the authentication service."""

    config = AuthConfig()
    service = AuthService(config=config)
    app.state.auth_service = service
    logging.info("Authentication Service Ready.")
