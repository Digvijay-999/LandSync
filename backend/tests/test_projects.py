import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_get_project(client: AsyncClient):
    """Test full CRUD lifecycle for minimal Project validation model."""
    # 1. Create project
    payload = {
        "name": "District 7 Cadastral Harmonization",
        "description": "Harmonizing drone survey with municipal parcel registry",
        "target_crs": "EPSG:32643",
        "status": "draft",
    }
    create_res = await client.post("/api/v1/projects", json=payload)
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()
    assert created["name"] == payload["name"]
    assert created["target_crs"] == "EPSG:32643"
    assert "id" in created
    project_id = created["id"]

    # 2. List projects
    list_res = await client.get("/api/v1/projects")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(p["id"] == project_id for p in list_data["items"])

    # 3. Get single project
    get_res = await client.get(f"/api/v1/projects/{project_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == project_id

    # 4. Update project
    update_res = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "District 7 Cadastral Harmonization (Updated)", "status": "processing"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "District 7 Cadastral Harmonization (Updated)"
    assert update_res.json()["status"] == "processing"

    # 5. Delete project
    del_res = await client.delete(f"/api/v1/projects/{project_id}")
    assert del_res.status_code == 204

    # 6. Verify 404 after deletion
    get_after_del = await client.get(f"/api/v1/projects/{project_id}")
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_project(client: AsyncClient):
    """Verify 404 response for unknown project ID."""
    random_id = uuid.uuid4()
    response = await client.get(f"/api/v1/projects/{random_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["error"]["message"].lower()
