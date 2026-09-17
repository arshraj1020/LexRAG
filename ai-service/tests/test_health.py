"""
Health endpoint smoke test.

Run: pytest tests/test_health.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_public_health():
    """Public /health endpoint returns 200 without an API key."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "lexrag-ai-service"


@pytest.mark.asyncio
async def test_internal_endpoint_requires_api_key():
    """/internal/* returns 422/403 when the API key header is missing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/internal/health")
    # 422 = missing required header; 403 = wrong key. Both mean the guard works.
    assert response.status_code in (403, 422)
