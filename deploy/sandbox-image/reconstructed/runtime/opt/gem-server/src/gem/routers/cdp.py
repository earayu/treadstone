import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union, cast
from urllib.parse import urlparse

import httpx
import websockets
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)


# --- 1. Configuration Class ---


class CDPProxyConfig:
    """
    Encapsulates all configuration logic for the CDP proxy service.
    """

    def __init__(
        self,
        cdp_origin_env: str = "CDP_TARGET_ORIGIN",
        cdp_netloc_env: str = "CDP_TARGET_NETLOC",
        custom_command_domain: str = "CDPProxy",
        websocket_max_size: int = 20 * 1024 * 1024,
        websocket_ping_interval: int = 20,
        websocket_ping_timeout: int = 20,
    ):
        """
        Initialize CDP proxy configuration.

        Args:
            cdp_origin_env: Environment variable name for CDP origin
            cdp_netloc_env: Environment variable name for CDP netloc
            custom_command_domain: Domain for custom CDP commands
            websocket_max_size: Maximum WebSocket message size
            websocket_ping_interval: WebSocket ping interval in seconds
            websocket_ping_timeout: WebSocket ping timeout in seconds
        """
        self.custom_command_domain = custom_command_domain
        self.websocket_max_size = websocket_max_size
        self.websocket_ping_interval = websocket_ping_interval
        self.websocket_ping_timeout = websocket_ping_timeout

        # Load configuration from environment
        self.cdp_origin = self._load_env_var(cdp_origin_env, "CDP_TARGET_ORIGIN")
        self.cdp_netloc = self._load_env_var(cdp_netloc_env, "CDP_TARGET_NETLOC")

        # Validate configuration
        self._validate_config()

    def _load_env_var(self, env_var: str, description: str) -> Optional[str]:
        """Load environment variable with logging."""
        value = os.environ.get(env_var)
        if not value:
            logging.warning(
                f"Environment variable '{env_var}' ({description}) is not set."
            )
        else:
            logging.info(f"Loaded {description}: {value}")
        return value

    def _validate_config(self) -> None:
        """Validate the loaded configuration."""
        if not self.cdp_origin:
            logging.error("CDP_TARGET_ORIGIN is required for CDP proxy functionality")

        if self.cdp_origin and not self.cdp_netloc:
            # Try to extract netloc from origin
            parsed = urlparse(self.cdp_origin)
            if parsed.netloc:
                self.cdp_netloc = parsed.netloc
                logging.info(f"Extracted CDP netloc from origin: {self.cdp_netloc}")

    def is_configured(self) -> bool:
        """Check if the configuration is valid for proxy operations."""
        return bool(self.cdp_origin and self.cdp_netloc)


# --- 2. Service Class ---


@dataclass
class LoggingState:
    """A mutable container for tracking the logging state of a WebSocket session."""

    enabled: bool = False


class CDPProxyService:
    """
    Main CDP proxy service that orchestrates all components.
    """

    def __init__(self, config: CDPProxyConfig):
        self.config = config
        self.http_client: Optional[httpx.AsyncClient] = None
        self.ws_url_pattern = re.compile(r'"(ws[s]?://)([^/]+)(/devtools/[^"]*)"')

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient()
            logging.info("HTTP client initialized for CDP proxy")
        return self.http_client

    async def close(self) -> None:
        """Close and cleanup resources."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
            logging.info("HTTP client closed for CDP proxy")

    async def handle_http_request(self, request: Request, path: str = "") -> Response:
        """Handle HTTP requests to CDP JSON endpoints."""
        if not self.config.is_configured():
            raise HTTPException(
                status_code=503, detail="CDP proxy is not properly configured"
            )

        http_client = await self.get_http_client()
        prefix = request.headers.get("x-forwarded-prefix", "")

        try:
            # Prepare headers
            headers = {
                key: value
                for key, value in request.headers.items()
                if key.lower() not in ("host", "accept-encoding")
            }
            if self.config.cdp_netloc:
                headers["Host"] = self.config.cdp_netloc

            logging.info(
                f"CDP request to {self.config.cdp_origin}{request.url.path}\n"
                f"\toriginal url: {request.url}\n"
                f"\toriginal path: {prefix}{request.url.path}\n"
                f"\toriginal headers: {request.headers}"
            )

            # Make upstream request
            response = await http_client.get(
                f"{self.config.cdp_origin}{request.url.path}", headers=headers
            )

            # Forward error responses directly
            if response.status_code != 200:
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=response.headers,
                )

            # Rewrite WebSocket URLs in response
            original_body = response.text
            proxy_host = request.headers.get("host", request.url.netloc)
            ws_protocol = "wss" if request.url.scheme == "https" else "ws"

            modified_body = self._rewrite_websocket_urls(
                original_body, proxy_host, prefix, ws_protocol
            )

            return Response(
                content=modified_body,
                status_code=response.status_code,
                media_type=response.headers.get("content-type"),
            )

        except httpx.TimeoutException:
            logging.error("CDP request timeout")
            raise HTTPException(status_code=504, detail="CDP request timeout")
        except httpx.RequestError as e:
            logging.error(f"CDP request error: {e}")
            raise HTTPException(status_code=502, detail="CDP connection failed")
        except Exception as e:
            logging.error(f"Unexpected error in CDP proxy: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

    async def handle_websocket_request(self, websocket: WebSocket, path: str) -> None:
        """Handle WebSocket connections to CDP."""
        if not self.config.is_configured():
            await websocket.close(code=1011, reason="CDP proxy not configured")
            return

        await websocket.accept()

        # Initialize logging state for this connection
        initial_state = logging.getLogger().isEnabledFor(logging.DEBUG)
        logging_state = LoggingState(enabled=initial_state)

        cdp_ws_url = f"ws://{self.config.cdp_netloc}/devtools/{path}"
        logging.info(f"Establishing CDP WebSocket connection to: {cdp_ws_url}")

        try:
            async with websockets.connect(
                cdp_ws_url,
                compression=None,
                max_size=self.config.websocket_max_size,
                ping_interval=self.config.websocket_ping_interval,
                ping_timeout=self.config.websocket_ping_timeout,
            ) as cdp_ws:
                logging.info(f"Connected to CDP WebSocket for path: /{path}")

                # Create bidirectional forwarding tasks
                client_to_cdp_task = asyncio.create_task(
                    self._forward_client_to_cdp(websocket, cdp_ws, path, logging_state)
                )
                cdp_to_client_task = asyncio.create_task(
                    self._forward_cdp_to_client(cdp_ws, websocket, path, logging_state)
                )

                # Wait for any task to complete
                done, pending = await asyncio.wait(
                    {client_to_cdp_task, cdp_to_client_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel and cleanup remaining tasks
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

                logging.info(f"CDP WebSocket proxy finished for path: /{path}")

        except websockets.exceptions.InvalidURI:
            logging.error(
                f"Invalid CDP WebSocket URI: {cdp_ws_url}"
            )  # pragma: no cover
            await websocket.close(
                code=1011, reason="Invalid upstream WebSocket URI"
            )  # pragma: no cover
        except websockets.exceptions.ConnectionClosed as e:
            logging.info(
                f"CDP WebSocket connection closed for path /{path}: {e}"
            )  # pragma: no cover
            await websocket.close(code=e.code, reason=str(e.reason))  # pragma: no cover
        except Exception as e:
            logging.error(
                f"Error in CDP WebSocket proxy for /{path}: {e}", exc_info=True
            )
            await websocket.close(code=1011, reason="Internal server error")
        finally:
            if websocket.client_state.name != "DISCONNECTED":
                try:
                    await websocket.close()
                except RuntimeError:
                    pass

    def _rewrite_websocket_urls(
        self, content: str, proxy_host: str, prefix: str, ws_protocol: str
    ) -> str:
        """
        Rewrite WebSocket URLs in CDP JSON response.
        """

        def replace_func(match: re.Match[str]) -> str:
            path_part = match.group(3)
            new_url = f'"{ws_protocol}://{proxy_host}{prefix}{path_part}"'
            logging.info(
                f"Rewriting WebSocket URL: {match.group(0)[1:-1]} -> {new_url[1:-1]}"
            )
            return new_url

        return self.ws_url_pattern.sub(replace_func, content)

    async def _handle_custom_command(
        self, data: str, websocket: WebSocket, path: str, logging_state: LoggingState
    ) -> bool:
        """
        Handle potential custom command message.
        """
        if self.config.custom_command_domain not in data:
            return False

        try:
            msg_json = json.loads(data)
            method = msg_json.get("method")

            if not isinstance(method, str) or not method.startswith(
                f"{self.config.custom_command_domain}."
            ):
                return False

            command_id = msg_json.get("id")
            params = msg_json.get("params", {})

            if method == f"{self.config.custom_command_domain}.setLoggingEnabled":
                enabled = bool(params.get("enabled", False))
                logging_state.enabled = enabled
                status = "Enabled" if enabled else "Disabled"
                logging.info(f"Logging for session /{path} {status} by command.")
                await self._send_success_response(websocket, command_id)
                return True
            else:
                logging.warning(f"Received unknown custom command: {method}")
                await self._send_error_response(
                    websocket, command_id, -32601, "Method not found"
                )
                return True

        except (json.JSONDecodeError, AttributeError):
            return False

    async def _send_success_response(
        self,
        websocket: WebSocket,
        command_id: Optional[int],
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send a standard CDP success response."""
        if result is None:
            result = {}
        await websocket.send_json({"id": command_id, "result": result})

    async def _send_error_response(
        self, websocket: WebSocket, command_id: Optional[int], code: int, message: str
    ) -> None:
        """Send a standard CDP error response."""
        await websocket.send_json(
            {"id": command_id, "error": {"code": code, "message": message}}
        )

    async def _forward_client_to_cdp(
        self,
        client_ws: WebSocket,
        cdp_ws: websockets.ClientConnection,
        path: str,
        logging_state: LoggingState,
    ) -> None:
        """Forward messages from client to CDP."""
        try:
            while True:
                message = await client_ws.receive()
                if message["type"] == "websocket.receive":
                    data = message.get("text") or message.get("bytes")
                    if data is None:
                        continue  # pragma: no cover

                    # Handle custom commands
                    if isinstance(data, str):
                        if await self._handle_custom_command(
                            data, client_ws, path, logging_state
                        ):
                            continue

                    # Log if enabled
                    if logging_state.enabled:
                        if isinstance(data, str):
                            logging.info(f"💻 /{path}: {data[:250]}...")
                        else:
                            logging.info(f"💻 /{path}: bytes of len {len(data)}")

                    await cdp_ws.send(data)

                elif message["type"] == "websocket.disconnect":
                    code = message.get("code", 1000)
                    reason = message.get("reason", "")
                    logging.info(
                        f"💻 Client disconnected from /{path}: [{code}] {reason}"
                    )
                    break

        except websockets.exceptions.ConnectionClosed:
            logging.info(
                f"🌐 CDP connection closed while sending from client: /{path}"
            )  # pragma: no cover
        except asyncio.CancelledError:
            pass
        except Exception as e:  # pragma: no cover
            logging.error(
                f"Error forwarding client to CDP /{path}: {e}", exc_info=True
            )  # pragma: no cover

    async def _forward_cdp_to_client(
        self,
        cdp_ws: websockets.ClientConnection,
        client_ws: WebSocket,
        path: str,
        logging_state: LoggingState,
    ) -> None:
        """Forward messages from CDP to client."""
        try:
            async for message in cdp_ws:
                # Log if enabled
                if logging_state.enabled:
                    log_data = (
                        message
                        if isinstance(message, str)
                        else f"bytes of len {len(message)}"
                    )
                    logging.info(f"🌐 /{path}: {log_data[:200]}...")

                if isinstance(message, str):
                    await client_ws.send_text(message)
                else:
                    await client_ws.send_bytes(message)

        except WebSocketDisconnect:
            logging.info(
                f"💻 Client disconnected while forwarding from CDP: /{path}"
            )  # pragma: no cover
        except websockets.exceptions.ConnectionClosed:
            logging.info(
                f"🌐 CDP connection closed while receiving: /{path}"
            )  # pragma: no cover
        except asyncio.CancelledError:
            pass
        except Exception as e:  # pragma: no cover
            logging.error(
                f"Error forwarding CDP to client /{path}: {e}", exc_info=True
            )  # pragma: no cover


# --- 3. Dependency Injection Setup ---


def _get_shared_cdp_service(context: Union[Request, WebSocket]) -> CDPProxyService:
    """Internal logic to retrieve the service from app.state."""
    app = context.app
    if not hasattr(app.state, "cdp_service"):
        raise HTTPException(
            status_code=503, detail="CDP proxy service is not available."
        )
    return cast(CDPProxyService, app.state.cdp_service)


async def get_cdp_service_for_http(request: Request) -> CDPProxyService:
    """Dependency provider for HTTP endpoints."""
    return _get_shared_cdp_service(request)


async def get_cdp_service_for_ws(websocket: WebSocket) -> CDPProxyService:
    """Dependency provider for WebSocket endpoints."""
    return _get_shared_cdp_service(websocket)


# --- 4. API Router ---

router = APIRouter()


@router.api_route("/json", methods=["GET", "POST"])
@router.api_route("/json/{path:path}", methods=["GET", "POST"])
async def cdp_http_proxy(
    request: Request,
    path: str = "",
    service: CDPProxyService = Depends(get_cdp_service_for_http),
) -> Response:
    """Proxy CDP /json endpoint using robust string replacement."""
    return await service.handle_http_request(request, path)


@router.websocket("/devtools/{path:path}")
async def cdp_websocket_proxy(
    websocket: WebSocket,
    path: str,
    service: CDPProxyService = Depends(get_cdp_service_for_ws),
) -> None:
    """Proxy CDP WebSocket connections for any devtools path."""
    await service.handle_websocket_request(websocket, path)


# --- 5. Lifecycle Management ---


async def startup(app: FastAPI) -> None:
    """Initialize the CDP proxy service."""

    config = CDPProxyConfig()
    service = CDPProxyService(config=config)
    app.state.cdp_service = service
    logging.info("CDP proxy service ready")


async def shutdown(app: FastAPI) -> None:
    """Shutdown the CDP proxy service."""
    if hasattr(app.state, "cdp_service"):
        await app.state.cdp_service.close()
    logging.info("CDP proxy service shutdown complete")
