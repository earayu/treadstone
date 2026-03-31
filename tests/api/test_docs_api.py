from treadstone.docs_manifest import load_docs_manifest


async def test_markdown_requests_succeed_for_all_manifest_pages(client):
    for entry in load_docs_manifest():
        response = await client.get(f"/docs/{entry.slug}", headers={"Accept": "text/markdown"})

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert response.text.strip()


async def test_docs_route_redirects_to_spa_for_all_manifest_pages(client):
    for entry in load_docs_manifest():
        response = await client.get(f"/docs/{entry.slug}", follow_redirects=False)

        assert response.status_code == 302
        assert response.headers["location"] == f"/docs?page={entry.slug}"


async def test_docs_sitemap_markdown_endpoint_serves_generated_sitemap(client):
    response = await client.get("/docs/sitemap.md", headers={"Accept": "text/markdown"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# Treadstone Documentation Sitemap" in response.text


async def test_unknown_slug_returns_markdown_404_and_spa_redirect(client):
    markdown_response = await client.get("/docs/not-a-real-page", headers={"Accept": "text/markdown"})
    browser_response = await client.get("/docs/not-a-real-page", follow_redirects=False)

    assert markdown_response.status_code == 404
    assert "not-a-real-page" in markdown_response.text
    assert browser_response.status_code == 302
    assert browser_response.headers["location"] == "/docs"


async def test_alias_slug_serves_canonical_content_and_redirect(client):
    markdown_response = await client.get("/docs/quickstart-human", headers={"Accept": "text/markdown"})
    browser_response = await client.get("/docs/quickstart-human", follow_redirects=False)

    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-location"] == "/docs/index"
    assert "# Overview" in markdown_response.text
    assert browser_response.status_code == 302
    assert browser_response.headers["location"] == "/docs?page=index"
