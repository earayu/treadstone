"""Run inside a sandbox container on CI; no image building is performed here."""

import asyncio
import importlib.util
import io
import json
import os
import shutil
import socket
from pathlib import Path

import httpx
import websockets
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from PIL import Image

BASE = "http://127.0.0.1:8080"


async def check_websockets() -> None:
    async with websockets.connect("ws://127.0.0.1:8080/v1/shell/ws") as ws:
        async with asyncio.timeout(30):
            while json.loads(await ws.recv())["type"] != "ready":
                pass
            await ws.send(json.dumps({"type": "input", "data": "printf 'ws-%s-ok\\n' terminal\r"}))
            output = ""
            while "ws-terminal-ok" not in output:
                message = json.loads(await ws.recv())
                if message["type"] == "output":
                    output += message["data"]
    async with httpx.AsyncClient() as client:
        info = (await client.get(f"{BASE}/cdp/json/version")).json()
    async with websockets.connect(info["webSocketDebuggerUrl"]) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Browser.getVersion"}))
        result = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        assert result["id"] == 1 and "product" in result["result"], result
    async with websockets.connect("ws://127.0.0.1:8080/websockify") as ws:
        greeting = await asyncio.wait_for(ws.recv(), timeout=10)
        assert greeting.startswith(b"RFB "), greeting


async def check_mcp() -> None:
    async with streamablehttp_client(f"{BASE}/mcp/") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {tool.name for tool in (await session.list_tools()).tools}
            assert {"browser_screenshot", "get_browser_info", "execute_bash"} <= names, names
            assert not any("jupyter" in name or "code_execute" in name or "markdown" in name for name in names)
            result = await session.call_tool("execute_bash", {"cmd": "printf mcp-ok"})
            assert not result.isError and "mcp-ok" in result.model_dump_json(), result


async def main() -> None:
    assert os.getuid() == 1000
    assert os.environ["HOME"] == "/home/gem"
    for command in ("code-server", "jupyter", "mcp-hub", "mcp-server-browser"):
        assert shutil.which(command) is None, command
    for module in ("jupyterlab", "ipykernel", "jupyter_client"):
        assert importlib.util.find_spec(module) is None, module
    for port in (8200, 8888, 8079, 8100, 8118):
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0, port

    async with httpx.AsyncClient(base_url=BASE, timeout=120) as client:
        for _ in range(180):
            try:
                response = await client.get("/health")
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
        else:
            raise AssertionError("Sandbox did not become healthy")

        for path in ("/", "/terminal", "/vnc/index.html"):
            response = await client.get(path)
            assert response.status_code == 200, (path, response.text)
        for path in ("/jupyter", "/jupyter/", "/code-server/", "/v1/jupyter/info", "/v1/code/info", "/v1/nodejs/info"):
            response = await client.get(path)
            assert response.status_code == 404, (path, response.status_code)

        spec = (await client.get("/v1/openapi.json")).json()
        expected = json.loads(Path("/tmp/sandbox_openapi_base.json").read_text())
        spec["info"]["version"] = expected["info"]["version"]
        assert spec == expected, "Published OpenAPI snapshot differs from the image"
        result = (
            await client.post(
                "/v1/shell/exec",
                json={
                    "command": "id -u && python3 -c 'print(6 * 7)' && node -e 'console.log(7 * 8)'",
                    "exec_dir": "/home/gem",
                },
            )
        ).json()
        assert result["success"] and result["data"]["status"] == "completed", result
        assert all(value in result["data"]["output"] for value in ("1000", "42", "56")), result

        result = (
            await client.post("/v1/file/write", json={"file": "/home/gem/smoke.txt", "content": "runtime-ok"})
        ).json()
        assert result["success"], result
        result = (await client.post("/v1/file/read", json={"file": "/home/gem/smoke.txt"})).json()
        assert result["data"]["content"] == "runtime-ok", result
        result = (
            await client.post(
                "/v1/file/str_replace_editor",
                json={
                    "command": "str_replace",
                    "path": "/home/gem/smoke.txt",
                    "old_str": "runtime-ok",
                    "new_str": "edited-ok",
                },
            )
        ).json()
        assert result["success"], result
        info = (await client.get("/v1/browser/info")).json()
        assert info["success"] and "/cdp/" in info["data"]["cdp_url"], info
        screenshot = await client.get("/v1/browser/screenshot")
        screenshot.raise_for_status()
        image = Image.open(io.BytesIO(screenshot.content)).convert("RGB")
        assert image.width >= 800 and image.height >= 600
        assert any(high > low for low, high in image.getextrema()), "Browser display is blank"

    await check_websockets()
    await check_mcp()
    print("Browser, shell, files, CDP, VNC, MCP and removed-service checks passed")


if __name__ == "__main__":
    asyncio.run(main())
