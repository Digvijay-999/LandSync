import io
import json
import zipfile
import uuid
import pytest
from httpx import AsyncClient
import geopandas as gpd
from shapely.geometry import Polygon, Point


@pytest.fixture
def sample_geojson_bytes() -> bytes:
    data = {
        "type": "FeatureCollection",
        "name": "test_parcels",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": [
            {
                "type": "Feature",
                "properties": {"parcel_id": "P-101", "zone": "Commercial", "value": 150000},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10.0, 20.0], [15.0, 20.0], [15.0, 25.0], [10.0, 25.0], [10.0, 20.0]]]
                }
            },
            {
                "type": "Feature",
                "properties": {"parcel_id": "P-102", "zone": "Residential", "value": 85000},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[16.0, 20.0], [20.0, 20.0], [20.0, 25.0], [16.0, 25.0], [16.0, 20.0]]]
                }
            }
        ]
    }
    return json.dumps(data).encode("utf-8")


@pytest.fixture
def sample_invalid_geometry_geojson_bytes() -> bytes:
    """Contains a self-intersecting (bow-tie) polygon which is invalid."""
    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "INV-1"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0.0, 0.0], [0.0, 2.0], [2.0, 0.0], [2.0, 2.0], [0.0, 0.0]]]
                }
            }
        ]
    }
    return json.dumps(data).encode("utf-8")


@pytest.fixture
def sample_csv_bytes() -> bytes:
    csv_text = (
        "station_id,name,latitude,longitude,capacity\n"
        "ST-01,Central Station,18.5204,73.8567,500\n"
        "ST-02,East Terminal,18.5310,73.8720,250\n"
        "ST-03,North Hub,18.5450,73.8410,320\n"
    )
    return csv_text.encode("utf-8")


@pytest.fixture
def sample_shapefile_zip_bytes(tmp_path) -> bytes:
    """Generates a real minimal Shapefile archive inside a zip buffer."""
    df = gpd.GeoDataFrame(
        {
            "id": ["SHP-1", "SHP-2"],
            "category": ["Zone A", "Zone B"],
            "geometry": [
                Polygon([(73.85, 18.52), (73.86, 18.52), (73.86, 18.53), (73.85, 18.53), (73.85, 18.52)]),
                Polygon([(73.87, 18.52), (73.88, 18.52), (73.88, 18.53), (73.87, 18.53), (73.87, 18.52)]),
            ],
        },
        crs="EPSG:4326",
    )
    shp_path = tmp_path / "test_zones.shp"
    df.to_file(shp_path)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        for p in tmp_path.glob("test_zones.*"):
            zf.write(p, arcname=p.name)
    zip_buf.seek(0)
    return zip_buf.getvalue()


@pytest.mark.asyncio
async def test_geojson_ingestion_and_profiling(client: AsyncClient, sample_geojson_bytes: bytes):
    """Test full ingestion lifecycle for GeoJSON file."""
    # 1. Create project
    proj_res = await client.post("/api/v1/projects", json={"name": "Parcels Harmonization"})
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Upload GeoJSON
    files = {"file": ("parcels.geojson", sample_geojson_bytes, "application/geo+json")}
    data = {"name": "Cadastral Parcels"}
    upload_res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files, data=data)
    assert upload_res.status_code == 201, upload_res.text
    ds = upload_res.json()

    assert ds["name"] == "Cadastral Parcels"
    assert ds["source_format"] == "geojson"
    assert ds["feature_count"] == 2
    assert ds["geometry_type"] == "Polygon"
    assert ds["detected_crs"] == "EPSG:4326"
    assert ds["bounding_box"] == {"min_x": 10.0, "min_y": 20.0, "max_x": 20.0, "max_y": 25.0}

    # Verify profile payload
    profile = ds["profile"]
    assert profile is not None
    assert profile["general"]["feature_count"] == 2
    assert profile["geometry"]["valid_geometry_count"] == 2
    assert profile["geometry"]["invalid_geometry_count"] == 0
    assert profile["geometry"]["validity_percentage"] == 100.0
    assert profile["spatial"]["bounds"]["min_x"] == 10.0
    assert len(profile["attributes"]["fields"]) == 3  # parcel_id, zone, value

    dataset_id = ds["id"]

    # 3. Retrieve dataset profile via dedicated endpoint
    prof_res = await client.get(f"/api/v1/datasets/{dataset_id}/profile")
    assert prof_res.status_code == 200
    assert prof_res.json()["geometry"]["geometry_type"] == "Polygon"

    # 4. List project datasets
    list_res = await client.get(f"/api/v1/projects/{project_id}/datasets")
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 1


@pytest.mark.asyncio
async def test_csv_coordinates_ingestion(client: AsyncClient, sample_csv_bytes: bytes):
    """Test CSV ingestion with automatic coordinate column detection and Point generation."""
    proj_res = await client.post("/api/v1/projects", json={"name": "Transit Analysis"})
    project_id = proj_res.json()["id"]

    files = {"file": ("transit_stations.csv", sample_csv_bytes, "text/csv")}
    upload_res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert upload_res.status_code == 201, upload_res.text
    ds = upload_res.json()

    assert ds["source_format"] == "csv"
    assert ds["feature_count"] == 3
    assert ds["geometry_type"] == "Point"
    assert ds["detected_crs"] == "EPSG:4326"
    assert ds["bounding_box"]["min_x"] == 73.8410
    assert ds["bounding_box"]["min_y"] == 18.5204


@pytest.mark.asyncio
async def test_shapefile_zip_ingestion(client: AsyncClient, sample_shapefile_zip_bytes: bytes):
    """Test Shapefile ZIP ingestion with extraction, companion validation, and profiling."""
    proj_res = await client.post("/api/v1/projects", json={"name": "Zoning Districts"})
    project_id = proj_res.json()["id"]

    files = {"file": ("zones.zip", sample_shapefile_zip_bytes, "application/zip")}
    upload_res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert upload_res.status_code == 201, upload_res.text
    ds = upload_res.json()

    assert ds["source_format"] == "shapefile"
    assert ds["feature_count"] == 2
    assert ds["geometry_type"] == "Polygon"


@pytest.mark.asyncio
async def test_invalid_geometry_profiling(client: AsyncClient, sample_invalid_geometry_geojson_bytes: bytes):
    """Test that invalid geometries are detected and recorded without failing the ingestion."""
    proj_res = await client.post("/api/v1/projects", json={"name": "Quality Audit"})
    project_id = proj_res.json()["id"]

    files = {"file": ("invalid_geom.geojson", sample_invalid_geometry_geojson_bytes, "application/geo+json")}
    upload_res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert upload_res.status_code == 201
    ds = upload_res.json()

    profile = ds["profile"]
    assert profile["geometry"]["invalid_geometry_count"] == 1
    assert profile["geometry"]["valid_geometry_count"] == 0
    assert profile["geometry"]["validity_percentage"] == 0.0


@pytest.mark.asyncio
async def test_unsupported_format_rejection(client: AsyncClient):
    """Test uploading an unsupported format returns 400 Bad Request."""
    proj_res = await client.post("/api/v1/projects", json={"name": "Validation Test"})
    project_id = proj_res.json()["id"]

    files = {"file": ("document.pdf", b"%PDF-1.4 fake binary content", "application/pdf")}
    res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert res.status_code == 400
    assert "unsupported file format" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_csv_missing_coordinates_rejection(client: AsyncClient):
    """Test CSV without recognizable lat/lon columns returns 400 Bad Request."""
    proj_res = await client.post("/api/v1/projects", json={"name": "Missing Coords"})
    project_id = proj_res.json()["id"]

    no_coords_csv = b"name,category,rating\nCafe,Food,4.5\nGym,Fitness,4.0\n"
    files = {"file": ("places.csv", no_coords_csv, "text/csv")}
    res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert res.status_code == 400
    assert "could not automatically identify latitude and longitude" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_corrupted_geojson_rejection(client: AsyncClient):
    """Test malformed GeoJSON file returns 422 Unprocessable Entity."""
    proj_res = await client.post("/api/v1/projects", json={"name": "Corrupt Test"})
    project_id = proj_res.json()["id"]

    corrupt_json = b"{ not a valid json syntax at all ]"
    files = {"file": ("broken.geojson", corrupt_json, "application/geo+json")}
    res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_upload_to_nonexistent_project(client: AsyncClient, sample_geojson_bytes: bytes):
    """Test uploading to a non-existent project returns 404 Not Found."""
    fake_project_id = uuid.uuid4()
    files = {"file": ("parcels.geojson", sample_geojson_bytes, "application/geo+json")}
    res = await client.post(f"/api/v1/projects/{fake_project_id}/datasets", files=files)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_geopackage_ingestion(client: AsyncClient, tmp_path):
    """Test GeoPackage vector ingestion and profiling."""
    proj_res = await client.post("/api/v1/projects", json={"name": "GeoPackage Project"})
    project_id = proj_res.json()["id"]

    df = gpd.GeoDataFrame(
        {
            "facility_id": ["FAC-01", "FAC-02"],
            "geometry": [Point(73.85, 18.52), Point(73.86, 18.53)],
        },
        crs="EPSG:4326",
    )
    gpkg_file = tmp_path / "facilities.gpkg"
    df.to_file(gpkg_file, driver="GPKG")

    files = {"file": ("facilities.gpkg", gpkg_file.read_bytes(), "application/geopackage+sqlite3")}
    res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert res.status_code == 201, res.text
    ds = res.json()
    assert ds["source_format"] == "geopackage"
    assert ds["feature_count"] == 2
    assert ds["geometry_type"] == "Point"


@pytest.mark.asyncio
async def test_delete_dataset(client: AsyncClient, sample_geojson_bytes: bytes):
    """Test dataset deletion removes record, versions, and storage."""
    proj_res = await client.post("/api/v1/projects", json={"name": "Deletion Test Project"})
    project_id = proj_res.json()["id"]

    files = {"file": ("to_delete.geojson", sample_geojson_bytes, "application/geo+json")}
    upload_res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert upload_res.status_code == 201
    dataset_id = upload_res.json()["id"]

    # Delete dataset
    del_res = await client.delete(f"/api/v1/datasets/{dataset_id}")
    assert del_res.status_code == 204

    # Verify 404
    get_res = await client.get(f"/api/v1/datasets/{dataset_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_empty_feature_collection_rejection(client: AsyncClient):
    """Test uploading an empty FeatureCollection returns 400 Bad Request."""
    proj_res = await client.post("/api/v1/projects", json={"name": "Empty FC Test"})
    project_id = proj_res.json()["id"]

    empty_fc = json.dumps({"type": "FeatureCollection", "features": []}).encode("utf-8")
    files = {"file": ("empty.geojson", empty_fc, "application/geo+json")}
    res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert res.status_code == 400
    assert "no valid spatial features" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_all_null_or_empty_geometry_rejection(client: AsyncClient):
    """Test uploading GeoJSON with only null or empty geometries returns 400 Bad Request."""
    proj_res = await client.post("/api/v1/projects", json={"name": "Null Geoms Test"})
    project_id = proj_res.json()["id"]

    null_geom_fc = json.dumps({
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": None, "properties": {"id": "1"}},
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": []}, "properties": {"id": "2"}}
        ]
    }).encode("utf-8")
    files = {"file": ("null_geoms.geojson", null_geom_fc, "application/geo+json")}
    res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert res.status_code == 400
    assert "no valid spatial features" in res.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_mixed_geometry_and_array_properties_ingestion(client: AsyncClient):
    """
    Test uploading GeoJSON with:
    - Multiple geometry types: Polygon, MultiPolygon, Point, LineString
    - Array/list properties (empty [] and populated ['tag1', 'tag2'])
    - A feature with null geometry alongside valid features
    Verifies that array truthiness errors do not occur and profiling classifies Mixed geometry.
    """
    proj_res = await client.post("/api/v1/projects", json={"name": "Mixed Geoms & Arrays Test"})
    project_id = proj_res.json()["id"]

    mixed_fc = json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "parcel_id": "P-MIX-1",
                    "tags": [],
                    "notes": ["surveyed", "approved"],
                    "meta": {"verified": True, "flags": []}
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.85, 18.52], [73.86, 18.52], [73.86, 18.53], [73.85, 18.53], [73.85, 18.52]]]
                }
            },
            {
                "type": "Feature",
                "properties": {
                    "parcel_id": "P-MIX-2",
                    "tags": ["structure"],
                    "notes": []
                },
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [
                        [[[73.87, 18.52], [73.88, 18.52], [73.88, 18.53], [73.87, 18.53], [73.87, 18.52]]]
                    ]
                }
            },
            {
                "type": "Feature",
                "properties": {
                    "parcel_id": "P-MIX-3",
                    "tags": ["tree", "landmark"]
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [73.855, 18.525]
                }
            },
            {
                "type": "Feature",
                "properties": {
                    "parcel_id": "P-MIX-4",
                    "tags": []
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[73.85, 18.52], [73.87, 18.54]]
                }
            },
            {
                "type": "Feature",
                "properties": {
                    "parcel_id": "P-MIX-5",
                    "tags": ["no_geometry"]
                },
                "geometry": None
            }
        ]
    }).encode("utf-8")

    files = {"file": ("mixed_parcels.geojson", mixed_fc, "application/geo+json")}
    res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert res.status_code == 201, res.text
    ds = res.json()
    assert ds["feature_count"] == 5
    assert ds["detected_crs"] == "EPSG:4326"

    profile = ds["profile"]
    assert profile["geometry"]["valid_geometry_count"] == 4
    assert profile["geometry"]["empty_geometry_count"] == 1
    assert profile["geometry"]["invalid_geometry_count"] == 0
    assert "Empty/None" in profile["geometry"]["geometry_type_distribution"]
    assert "Polygon" in profile["geometry"]["geometry_type_distribution"]
    assert "Point" in profile["geometry"]["geometry_type_distribution"]
    assert "LineString" in profile["geometry"]["geometry_type_distribution"]


@pytest.mark.asyncio
async def test_geojson_default_epsg4326_without_crs(client: AsyncClient):
    """Test GeoJSON without any CRS declaration defaults to EPSG:4326."""
    proj_res = await client.post("/api/v1/projects", json={"name": "CRS Default Test"})
    project_id = proj_res.json()["id"]

    fc_no_crs = json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Boundary"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.0, 18.0], [74.0, 18.0], [74.0, 19.0], [73.0, 19.0], [73.0, 18.0]]]
                }
            }
        ]
    }).encode("utf-8")

    files = {"file": ("wgs84_boundary.geojson", fc_no_crs, "application/geo+json")}
    res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert res.status_code == 201
    ds = res.json()
    assert ds["detected_crs"] == "EPSG:4326"


@pytest.mark.asyncio
async def test_pune_haveli_demo_parcels_full_ingestion(client: AsyncClient):
    """Test ingesting the actual 30-polygon Pune/Haveli demo dataset containing empty array properties."""
    from pathlib import Path
    pune_path = Path(__file__).resolve().parent / "pune_haveli_demo_parcels.geojson"
    if not pune_path.exists():
        demo_dir = Path(__file__).resolve().parent.parent.parent / "demo-data" / "synthetic"
        pune_path = demo_dir / "pune_haveli_demo_parcels.geojson"
    if not pune_path.exists():
        pune_path = Path(__file__).resolve().parent.parent / "pune_test.geojson"
    if not pune_path.exists():
        pune_path = Path("/app/pune_test.geojson")
    if not pune_path.exists():
        pytest.skip("pune_haveli_demo_parcels.geojson fixture not found.")

    proj_res = await client.post("/api/v1/projects", json={"name": "Pune Haveli Project"})
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    with open(pune_path, "rb") as f:
        files = {"file": ("pune_haveli_demo_parcels.geojson", f, "application/geo+json")}
        res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)

    assert res.status_code == 201, res.text
    ds = res.json()
    assert ds["feature_count"] == 30
    assert ds["geometry_type"] == "Polygon"
    assert ds["detected_crs"] == "EPSG:4326"
    assert ds["profile"]["geometry"]["valid_geometry_count"] == 30
    assert ds["profile"]["geometry"]["invalid_geometry_count"] == 0
    assert ds["profile"]["geometry"]["empty_geometry_count"] == 0


@pytest.mark.asyncio
async def test_pune_haveli_complete_read_path_regression(client: AsyncClient):
    """
    Regression test proving the complete read chain:
    INGEST -> DATABASE -> GET DATASETS API -> GET PROJECT LAYERS API -> GET GEOJSON
    Verifies:
    - dataset count = 1
    - feature count = 30
    - map layer endpoint returns 1 spatial layer with bounds and features
    """
    from pathlib import Path
    pune_path = Path(__file__).resolve().parent / "pune_haveli_demo_parcels.geojson"
    if not pune_path.exists():
        demo_dir = Path(__file__).resolve().parent.parent.parent / "demo-data" / "synthetic"
        pune_path = demo_dir / "pune_haveli_demo_parcels.geojson"
    if not pune_path.exists():
        pune_path = Path(__file__).resolve().parent.parent / "pune_test.geojson"
    if not pune_path.exists():
        pune_path = Path("/app/pune_test.geojson")
    if not pune_path.exists():
        pytest.skip("pune_haveli_demo_parcels.geojson fixture not found.")

    # 1. Create project
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "Pune Haveli Read Path Test", "target_crs": "EPSG:4326"}
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["id"]

    # 2. Ingest dataset
    with open(pune_path, "rb") as f:
        files = {"file": ("pune_haveli_demo_parcels.geojson", f, "application/geo+json")}
        ingest_res = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert ingest_res.status_code == 201, ingest_res.text
    ingested_ds = ingest_res.json()
    dataset_id = ingested_ds["id"]

    # 3. GET project datasets API
    list_res = await client.get(f"/api/v1/projects/{project_id}/datasets")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] == 1
    assert len(list_data["items"]) == 1
    ds_item = list_data["items"][0]
    assert ds_item["id"] == dataset_id
    assert ds_item["name"] == "pune_haveli_demo_parcels"
    assert ds_item["feature_count"] == 30
    assert ds_item["geometry_type"] == "Polygon"
    assert ds_item["status"] == "ready"
    assert ds_item["detected_crs"] == "EPSG:4326"

    # 4. GET project layers API (used by map workspace)
    layers_res = await client.get(f"/api/v1/projects/{project_id}/layers")
    assert layers_res.status_code == 200
    layers_data = layers_res.json()
    assert layers_data["project_id"] == project_id
    assert len(layers_data["layers"]) == 1
    layer = layers_data["layers"][0]
    assert layer["dataset_id"] == dataset_id
    assert layer["name"] == "pune_haveli_demo_parcels"
    assert layer["feature_count"] == 30
    assert layer["geometry_type"] == "Polygon"
    assert layer["bounds"] is not None
    assert layers_data["combined_bounds"] is not None

    # 5. GET dataset canonical features GeoJSON (rendered on the map)
    geojson_res = await client.get(f"/api/v1/datasets/{dataset_id}/features/geojson?representation=canonical")
    assert geojson_res.status_code == 200
    geojson_data = geojson_res.json()
    assert geojson_data["type"] == "FeatureCollection"
    assert len(geojson_data["features"]) == 30
    assert geojson_data["total"] == 30
    assert geojson_data["features"][0]["geometry"]["type"] == "Polygon"



