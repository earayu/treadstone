async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_health_no_db_field(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert "db" not in resp.json()
