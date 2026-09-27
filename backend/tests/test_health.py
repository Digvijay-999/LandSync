import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Verify application root metadata endpoint."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "LandSync AI"
    assert data["status"] == "online"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_endpoint_basic(client: AsyncClient):
    """Verify GET /api/health endpoint returns successful health payload."""
    response = await client.get("/api/health?check_db=false")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == "LandSync AI"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_health_endpoint_with_db_check(client: AsyncClient):
    """Verify GET /api/health includes database health structure."""
    response = await client.get("/api/health?check_db=true")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert data["database"] is not None
