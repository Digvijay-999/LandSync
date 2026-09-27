import uuid
import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from shapely.geometry import Point, Polygon

from app.models.project import Project
from app.models.feature import SourceFeature, CanonicalFeature
from app.services.crs.normalizer import (
    CRSNormalizer,
    MissingCRSError,
    InvalidCRSError,
    TransformationError,
)
from app.services.dataset import extract_shapely_geom


# ---------------------------------------------------------------------------
# 1. CRS Normalizer Tests
# ---------------------------------------------------------------------------

def test_crs_normalizer_authority_cleaning():
    assert CRSNormalizer.normalize_crs_string("epsg:4326") == "EPSG:4326"
    assert CRSNormalizer.normalize_crs_string("4326") == "EPSG:4326"
    assert CRSNormalizer.normalize_crs_string("WGS 84") == "EPSG:4326"
    assert CRSNormalizer.to_srid("EPSG:4326") == 4326
    assert CRSNormalizer.to_srid("EPSG:3857") == 3857
    assert CRSNormalizer.to_srid(None) == 4326


def test_crs_normalizer_missing_and_invalid_crs():
    with pytest.raises(MissingCRSError):
        CRSNormalizer.normalize_crs_string("")

    with pytest.raises(MissingCRSError):
        CRSNormalizer.normalize_crs_string(None)

    with pytest.raises(InvalidCRSError):
        CRSNormalizer.normalize_crs_string("EPSG:999999999")

    pt = Point(73.8567, 18.5204)
    with pytest.raises(MissingCRSError):
        CRSNormalizer.transform_geometry(pt, "", "EPSG:4326")


def test_crs_normalizer_transform_geometry():
    # Transform Pune coordinates from EPSG:4326 to Web Mercator (EPSG:3857)
    pt_4326 = Point(73.856744, 18.520430)
    pt_3857 = CRSNormalizer.transform_geometry(pt_4326, "EPSG:4326", "EPSG:3857")

    # In Web Mercator, Pune is around x ~ 8.22e6, y ~ 2.09e6
    assert 8_000_000 < pt_3857.x < 8_500_000
    assert 2_000_000 < pt_3857.y < 2_200_000

    # Transform back to EPSG:4326 and verify mathematical precision
    pt_back = CRSNormalizer.transform_geometry(pt_3857, "EPSG:3857", "EPSG:4326")
    assert pytest.approx(pt_back.x, abs=1e-5) == 73.856744
    assert pytest.approx(pt_back.y, abs=1e-5) == 18.520430


def test_crs_normalizer_polygon_transform():
    # Polygon in UTM Zone 43N (EPSG:32643)
    # Approx Pune coordinates in UTM Zone 43N: Easting ~ 379300, Northing ~ 2048000
    poly_utm = Polygon([
        (379300, 2048000),
        (379400, 2048000),
        (379400, 2048100),
        (379300, 2048100),
        (379300, 2048000),
    ])

    poly_4326 = CRSNormalizer.transform_geometry(poly_utm, "EPSG:32643", "EPSG:4326")
    assert poly_4326.geom_type == "Polygon"
    # Should be around lon 73.8, lat 18.5
    minx, miny, maxx, maxy = poly_4326.bounds
    assert 73.0 < minx < 74.0
    assert 18.0 < miny < 19.0


# ---------------------------------------------------------------------------
# 2. Integration Tests: Features Ingestion & APIs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feature_ingestion_and_canonicalization(client: AsyncClient, db_session: AsyncSession):
    # 1. Create a project with explicit target CRS EPSG:4326
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Feature Test Project", "target_crs": "EPSG:4326"},
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["id"]

    # 2. Upload GeoJSON dataset (2 parcels)
    geojson_payload = {
        "type": "FeatureCollection",
        "name": "cadastral_sample",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": [
            {
                "type": "Feature",
                "properties": {"parcel_id": "P-101", "owner": "Alice", "area_sqm": 450.5},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.85, 18.52], [73.86, 18.52], [73.86, 18.53], [73.85, 18.53], [73.85, 18.52]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"parcel_id": "P-102", "owner": "Bob", "area_sqm": 620.0},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.86, 18.52], [73.87, 18.52], [73.87, 18.53], [73.86, 18.53], [73.86, 18.52]]],
                },
            },
        ],
    }

    files = {"file": ("parcels.geojson", json.dumps(geojson_payload), "application/geo+json")}
    ds_resp = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files)
    assert ds_resp.status_code == 201
    ds_data = ds_resp.json()
    dataset_id = ds_data["id"]
    assert ds_data["feature_count"] == 2
    assert ds_data["status"] == "ready"

    # 3. Direct DB Check: SourceFeatures & CanonicalFeatures
    src_stmt = select(SourceFeature)
    src_res = await db_session.execute(src_stmt)
    src_feats = list(src_res.scalars().all())
    assert len(src_feats) == 2

    can_stmt = select(CanonicalFeature)
    can_res = await db_session.execute(can_stmt)
    can_feats = list(can_res.scalars().all())
    assert len(can_feats) == 2

    # Check traceability: CanonicalFeature source_feature_id maps to SourceFeature id
    src_ids = {sf.id for sf in src_feats}
    for cf in can_feats:
        assert cf.source_feature_id in src_ids
        assert cf.target_crs == "EPSG:4326"
        assert cf.source_crs == "EPSG:4326"
        assert "owner" in cf.canonical_properties

    # 4. GeoJSON API Check
    geo_resp = await client.get(f"/api/v1/datasets/{dataset_id}/features/geojson")
    assert geo_resp.status_code == 200
    geo_data = geo_resp.json()
    assert geo_data["type"] == "FeatureCollection"
    assert geo_data["total"] == 2
    assert len(geo_data["features"]) == 2
    assert geo_data["features"][0]["properties"]["_dataset_name"] == "parcels"
    assert geo_data["features"][0]["geometry"]["type"] == "Polygon"

    # 5. Features Paginated API Check
    feat_resp = await client.get(f"/api/v1/datasets/{dataset_id}/features?limit=1")
    assert feat_resp.status_code == 200
    feat_data = feat_resp.json()
    assert feat_data["total"] == 2
    assert len(feat_data["items"]) == 1
    assert feat_data["items"][0]["properties"]["parcel_id"] in ["P-101", "P-102"]


@pytest.mark.asyncio
async def test_crs_transformation_on_upload(client: AsyncClient, db_session: AsyncSession):
    # Create project in EPSG:4326
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "UTM Reprojection Project", "target_crs": "EPSG:4326"},
    )
    project_id = proj_resp.json()["id"]

    # Upload CSV in UTM Zone 43N (EPSG:32643) with explicit crs parameter
    csv_content = (
        "asset_id,easting,northing,facility_type\n"
        "AST-01,379350.5,2048050.2,Water Reservoir\n"
        "AST-02,379410.8,2048120.6,Substation\n"
    )
    files = {"file": ("assets_utm.csv", csv_content.encode("utf-8"), "text/csv")}
    data = {"crs": "EPSG:32643"}

    ds_resp = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files, data=data)
    assert ds_resp.status_code == 201
    dataset_id = ds_resp.json()["id"]
    assert ds_resp.json()["detected_crs"] == "EPSG:32643"

    # Verify Canonical features have been transformed to EPSG:4326 coordinates (~73.85, 18.52)
    geo_resp = await client.get(f"/api/v1/datasets/{dataset_id}/features/geojson?representation=canonical")
    assert geo_resp.status_code == 200
    features = geo_resp.json()["features"]
    assert len(features) == 2

    first_geom = features[0]["geometry"]
    assert first_geom["type"] == "Point"
    lon, lat = first_geom["coordinates"]
    # Check transformed coordinate ranges
    assert 73.0 < lon < 74.0
    assert 18.0 < lat < 19.0


@pytest.mark.asyncio
async def test_project_layers_api_and_combined_extent(client: AsyncClient):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Multi-Layer Project", "target_crs": "EPSG:4326"},
    )
    project_id = proj_resp.json()["id"]

    # Upload Layer 1: Parcels (Polygon)
    parcels_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Parcel Alpha"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.80, 18.50], [73.82, 18.50], [73.82, 18.52], [73.80, 18.52], [73.80, 18.50]]],
                },
            }
        ],
    }
    await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("parcels.geojson", json.dumps(parcels_geojson), "application/geo+json")},
    )

    # Upload Layer 2: Municipal Assets (Points)
    csv_content = "id,longitude,latitude,type\n1,73.85,18.55,Hydrant\n"
    await client.post(
        f"/api/v1/projects/{project_id}/datasets",
        files={"file": ("assets.csv", csv_content.encode("utf-8"), "text/csv")},
    )

    # Call Project Layers API
    layers_resp = await client.get(f"/api/v1/projects/{project_id}/layers")
    assert layers_resp.status_code == 200
    layers_data = layers_resp.json()

    assert layers_data["project_id"] == project_id
    assert layers_data["target_crs"] == "EPSG:4326"
    assert len(layers_data["layers"]) == 2

    # Check distinct layer colors and URLs
    colors = [layer["color"] for layer in layers_data["layers"]]
    assert len(set(colors)) == 2
    assert all("geojson_url" in layer for layer in layers_data["layers"])

    # Check combined bounding box encompasses both datasets (from 73.80 to 73.85, 18.50 to 18.55)
    bbox = layers_data["combined_bounds"]
    assert bbox is not None
    assert bbox["min_x"] <= 73.80
    assert bbox["max_x"] >= 73.85
    assert bbox["min_y"] <= 18.50
    assert bbox["max_y"] >= 18.55

    # Check Combined GeoJSON API
    comb_resp = await client.get(f"/api/v1/projects/{project_id}/features/geojson")
    assert comb_resp.status_code == 200
    comb_data = comb_resp.json()
    assert comb_data["total"] == 2
    types = {f["geometry"]["type"] for f in comb_data["features"]}
    assert "Polygon" in types
    assert "Point" in types


@pytest.mark.asyncio
async def test_invalid_crs_upload_rejection(client: AsyncClient):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Invalid CRS Test", "target_crs": "EPSG:4326"},
    )
    project_id = proj_resp.json()["id"]

    csv_content = "id,longitude,latitude\n1,73.85,18.52\n"
    files = {"file": ("data.csv", csv_content.encode("utf-8"), "text/csv")}
    # Pass an invalid CRS code
    data = {"crs": "EPSG:999999"}

    resp = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files, data=data)
    assert resp.status_code == 400
    assert "Failed to resolve coordinate reference system" in resp.json()["error"]["message"]


@pytest.mark.asyncio
async def test_transaction_rollback_on_failure(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    proj_resp = await client.post(
        "/api/v1/projects",
        json={"name": "Rollback Test Project", "target_crs": "EPSG:4326"},
    )
    project_id = proj_resp.json()["id"]

    # Mock CRSNormalizer.transform_geometry to raise an unexpected error during feature extraction
    from app.services.crs.normalizer import CRSNormalizer

    def raise_synthetic_error(*args, **kwargs):
        raise RuntimeError("Synthetic processing crash during canonicalization")

    monkeypatch.setattr(CRSNormalizer, "transform_geometry", raise_synthetic_error)

    # Dataset with non-4326 CRS will trigger transform_geometry
    csv_content = "id,x,y\n1,379350.5,2048050.2\n"
    files = {"file": ("rollback_data.csv", csv_content.encode("utf-8"), "text/csv")}
    data = {"crs": "EPSG:32643"}

    resp = await client.post(f"/api/v1/projects/{project_id}/datasets", files=files, data=data)
    assert resp.status_code == 500

    # Ensure no orphan records were committed
    src_res = await db_session.execute(select(SourceFeature))
    assert len(list(src_res.scalars().all())) == 0

    can_res = await db_session.execute(select(CanonicalFeature))
    assert len(list(can_res.scalars().all())) == 0

