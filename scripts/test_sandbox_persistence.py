"""Check file and persistent browser-cookie survival across container replacement."""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import websockets

MARKER = Path("/home/gem/.treadstone-persistence-check")
COOKIE = {"name": "treadstone_persistence", "value": "verified", "domain": "example.test", "path": "/"}


async def main(mode: str) -> None:
    async with httpx.AsyncClient(timeout=5) as client:
        for _ in range(180):
            try:
                response = await client.get("http://127.0.0.1:8080/cdp/json/version")
                response.raise_for_status()
                endpoint = response.json()["webSocketDebuggerUrl"]
                break
            except (httpx.HTTPError, KeyError):
                await asyncio.sleep(1)
        else:
            raise AssertionError("Browser did not become ready")
    async with websockets.connect(endpoint) as ws:
        if mode == "seed":
            MARKER.write_text("workspace-survives-replacement\n")
            method = "Storage.setCookies"
            params = {"cookies": [{**COOKIE, "expires": time.time() + 86400}]}
        else:
            assert MARKER.read_text() == "workspace-survives-replacement\n"
            method, params = "Storage.getCookies", {}
        await ws.send(json.dumps({"id": 1, "method": method, "params": params}))
        async with asyncio.timeout(20):
            while True:
                reply = json.loads(await ws.recv())
                if reply.get("id") == 1:
                    break
        assert "error" not in reply, reply
        if mode == "check":
            assert any(
                all(cookie.get(key) == value for key, value in COOKIE.items()) for cookie in reply["result"]["cookies"]
            ), reply
    print(f"Persistent workspace and browser cookie: {mode} passed")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("seed", "check"):
        raise SystemExit("Usage: test_sandbox_persistence.py seed|check")
    asyncio.run(main(sys.argv[1]))
