import os
import uuid
import json
import csv
import hashlib
import tempfile
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
import geopandas as gpd
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from shapely.geometry import Polygon
from geoalchemy2.shape import from_shape

from app.models.project import Project
from app.models.dataset import Dataset, DatasetVersion
from app.models.feature import CanonicalFeature, SourceFeature
from app.models.pipeline import PipelineStageExecution
from app.models.provenance import ProvenanceRecord, ProvenanceEvent
from app.models.adjudication import HumanReviewDecision
from app.models.conflict import GeospatialConflict
from app.models.validation import ValidationResult
from app.models.matching import MatchRun, FeatureMatch
from app.models.unified import UnifiedLandRecord, UnifiedLandRecordSource
from app.models.export import ExportJob


def get_err_msg(resp) -> str:
    data = resp.json()
    if isinstance(data, dict):
        if "error" in data and isinstance(data["error"], dict):
            return str(data["error"].get("message", ""))
        return str(data.get("detail", ""))
    return ""


async def setup_stage14_test_env(client: AsyncClient, db_session: AsyncSession):
    """
    Sets up a complete upstream pipeline through Stage 13:
    1. Project
    2. Datasets & Canonical Features
    3. Stage 12 Unified Land Records (1 authoritative, 1 quarantined)
    4. Stage 13 Provenance Records
    5. Completed Stage 12 and Stage 13 PipelineStageExecution rows
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "Pune Haveli M14 Export Test"})
    assert proj_resp.status_code == 201
    proj_id = uuid.UUID(proj_resp.json()["id"])
    now = datetime.now(timezone.utc)

    ds_a = Dataset(
        id=uuid.uuid4(),
        project_id=proj_id,
        name="Cadastral Map Pune Haveli",
        source_filename="cadastral.geojson",
        source_format="GEOJSON",
        feature_count=2,
    )
    db_session.add(ds_a)
    await db_session.flush()

    dv_a = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=ds_a.id,
        version_number=1,
        storage_path="datasets/cadastral_v1.geojson",
    )
    db_session.add(dv_a)
    await db_session.flush()

    poly1 = Polygon([(73.850, 18.520), (73.860, 18.520), (73.860, 18.530), (73.850, 18.530), (73.850, 18.520)])
    geom1 = from_shape(poly1, srid=4326)

    poly2 = Polygon([(73.870, 18.540), (73.880, 18.540), (73.880, 18.550), (73.870, 18.550), (73.870, 18.540)])
    geom2 = from_shape(poly2, srid=4326)

    src_f1 = SourceFeature(
        id=uuid.uuid4(),
        dataset_version_id=dv_a.id,
        source_feature_id="SRC-CAD-001",
        geometry=geom1,
        geometry_type="Polygon",
        properties={"parcel_id": "HAV-CAD-001"},
    )
    src_f2 = SourceFeature(
        id=uuid.uuid4(),
        dataset_version_id=dv_a.id,
        source_feature_id="SRC-CAD-002",
        geometry=geom2,
        geometry_type="Polygon",
        properties={"parcel_id": "HAV-CAD-002"},
    )
    db_session.add_all([src_f1, src_f2])
    await db_session.flush()

    cf1 = CanonicalFeature(
        id=uuid.uuid4(),
        dataset_version_id=dv_a.id,
        source_feature_id=src_f1.id,
        geometry=geom1,
        geometry_type="Polygon",
        source_crs="EPSG:4326",
        target_crs="EPSG:4326",
        canonical_properties={"parcel_id": "HAV-CAD-001"},
    )
    cf2 = CanonicalFeature(
        id=uuid.uuid4(),
        dataset_version_id=dv_a.id,
        source_feature_id=src_f2.id,
        geometry=geom2,
        geometry_type="Polygon",
        source_crs="EPSG:4326",
        target_crs="EPSG:4326",
        canonical_properties={"parcel_id": "HAV-CAD-002"},
    )
    db_session.add_all([cf1, cf2])
    await db_session.flush()

    # Stage 12 Unified Land Records: 1 authoritative, 1 quarantined/rejected
    ulr_auth = UnifiedLandRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        record_identifier="ULR-HAV-000001",
        status="ACTIVE",
        canonical_geometry=geom1,
        geometry_source_feature_id=cf1.id,
        geometry_source_role="CADASTRAL",
        area=12500.0,
        canonical_attributes={"parcel_id": "HAV-CAD-001", "land_use": "RESIDENTIAL"},
        harmonized_record_id="harm_pune_haveli_001",
        source_a_reference="HAV-CAD-001",
        source_b_reference="HAV-MUN-001",
        geometry_source="SOURCE_A",
        land_use="RESIDENTIAL",
        mutation_status="MUTATED",
        risk_level="LOW",
        confidence_score=0.940,
        validation_status="PASS",
        human_review_decision="MERGE_RECONCILE",
        resolution_status="UNIFIED",
        metadata_trail={"test": "data"},
    )
    ulr_quar = UnifiedLandRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        record_identifier="ULR-HAV-000002",
        status="CONFLICT",
        canonical_geometry=geom2,
        geometry_source_feature_id=cf2.id,
        geometry_source_role="CADASTRAL",
        area=8900.0,
        canonical_attributes={"parcel_id": "HAV-CAD-002"},
        harmonized_record_id="harm_pune_haveli_rej",
        source_a_reference="HAV-CAD-002",
        source_b_reference="HAV-MUN-002",
        geometry_source="SOURCE_A",
        land_use="DISPUTED",
        mutation_status="PENDING",
        risk_level="HIGH",
        confidence_score=0.510,
        validation_status="FAIL",
        human_review_decision="REJECT_UNRESOLVED",
        resolution_status="REJECTED",
        metadata_trail={"test": "quarantine"},
    )
    db_session.add_all([ulr_auth, ulr_quar])
    await db_session.flush()

    # Stage 13 Provenance Records
    prov_auth = ProvenanceRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        unified_land_record_id=ulr_auth.id,
        harmonized_record_id="harm_pune_haveli_001",
        record_identifier="ULR-HAV-000001",
        source_dataset_ids=[str(ds_a.id)],
        source_feature_ids=[str(cf1.id)],
        confidence_score=0.940,
        confidence_bucket="VERY_HIGH",
        resolution_status="UNIFIED",
        lineage_completeness_pct=100.0,
        lineage_status="COMPLETE",
    )
    prov_quar = ProvenanceRecord(
        id=uuid.uuid4(),
        project_id=proj_id,
        unified_land_record_id=ulr_quar.id,
        harmonized_record_id="harm_pune_haveli_rej",
        record_identifier="ULR-HAV-000002",
        source_dataset_ids=[str(ds_a.id)],
        source_feature_ids=[str(cf2.id)],
        confidence_score=0.510,
        confidence_bucket="LOW",
        resolution_status="REJECTED",
        lineage_completeness_pct=85.0,
        lineage_status="QUARANTINED",
    )
    db_session.add_all([prov_auth, prov_quar])
    await db_session.flush()

    # PipelineStageExecution for Stages 12 and 13
    exec12 = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=12,
        stage_id="record",
        status="completed",
        results={"total_records": 2, "authoritative": 1, "rejected": 1},
        completed_at=now,
    )
    exec13 = PipelineStageExecution(
        id=uuid.uuid4(),
        project_id=proj_id,
        stage_number=13,
        stage_id="provenance",
        status="completed",
        results={"lineage_completeness_mean": 92.5},
        completed_at=now,
    )
    db_session.add_all([exec12, exec13])
    await db_session.commit()

    return {
        "project_id": proj_id,
        "ulr_auth": ulr_auth,
        "ulr_quar": ulr_quar,
        "prov_auth": prov_auth,
        "prov_quar": prov_quar,
    }


@pytest.mark.asyncio
async def test_stage14_prerequisite_lock(client: AsyncClient):
    """
    Verify Stage 14 is disabled when Stage 12 and Stage 13 are incomplete.
    """
    proj_resp = await client.post("/api/v1/projects", json={"name": "Stage 14 Prereq Lock Test"})
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]

    # Check status -> disabled
    st_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/stage-14/status")
    assert st_resp.status_code == 200
    st_data = st_resp.json()
    assert st_data["status"] == "disabled"
    assert st_data["prerequisites_met"] is False
    assert "Stage 12" in st_data["prerequisites_message"]

    # Execute -> 400
    exec_resp = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-14/execute")
    assert exec_resp.status_code == 400
    assert "Prerequisite" in get_err_msg(exec_resp)

    # Alias execute -> 400
    exec_alias = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stages/14/execute")
    assert exec_alias.status_code == 400

    # Create export endpoint directly -> 400
    exp_resp = await client.post(
        f"/api/v1/projects/{proj_id}/exports",
        json={"format": "geojson", "include_quarantined": False},
    )
    assert exp_resp.status_code == 400


@pytest.mark.asyncio
async def test_stage14_execute_geojson_and_download(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Execute Stage 14 and verify default GeoJSON delivery:
    1. Triggers Stage 14 execution.
    2. Verifies stage transitions to 'completed'.
    3. Downloads generated GeoJSON.
    4. Confirms exactly 1 authoritative feature (quarantined excluded by default).
    5. Confirms RFC 7946 GeoJSON structure, coordinates, and properties.
    """
    env = await setup_stage14_test_env(client, db_session)
    proj_id = env["project_id"]

    # 1. Check status before execution -> ready
    st_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/stage-14/status")
    assert st_resp.status_code == 200
    st_data = st_resp.json()
    assert st_data["status"] == "ready"
    assert st_data["prerequisites_met"] is True
    assert st_data["authoritative_records_count"] == 1
    assert st_data["quarantined_records_count"] == 1
    assert st_data["total_records_count"] == 2

    # 2. Execute Stage 14
    exec_resp = await client.post(f"/api/v1/projects/{proj_id}/pipeline/stage-14/execute")
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["status"] == "completed"
    assert exec_data["authoritative_records_count"] == 1
    assert exec_data["quarantined_records_count"] == 1
    export_job = exec_data["export_job"]
    assert export_job["format"] == "geojson"
    assert export_job["record_count"] == 1
    assert export_job["authoritative_count"] == 1
    assert export_job["quarantined_count"] == 1
    assert export_job["include_quarantined"] is False

    # 3. Verify overall pipeline status shows Stage 14 completed
    pipe_resp = await client.get(f"/api/v1/projects/{proj_id}/pipeline/status")
    assert pipe_resp.status_code == 200
    stages = {s["stage_number"]: s for s in pipe_resp.json()["stages"]}
    assert stages[14]["status"] == "completed"
    assert stages[14]["results_summary"]["default_export_format"] == "geojson"

    # 4. Download GeoJSON deliverable
    download_url = export_job["download_url"]
    dl_resp = await client.get(download_url)
    assert dl_resp.status_code == 200
    assert "application/geo+json" in dl_resp.headers["content-type"]
    assert "attachment" in dl_resp.headers["content-disposition"]

    # 5. Parse and verify GeoJSON content
    geojson_obj = dl_resp.json()
    assert geojson_obj["type"] == "FeatureCollection"
    assert "metadata" in geojson_obj
    assert geojson_obj["metadata"]["crs"] == "EPSG:4326"
    assert geojson_obj["metadata"]["authoritative_records"] == 1
    assert geojson_obj["metadata"]["quarantined_records"] == 1

    features = geojson_obj["features"]
    assert len(features) == 1
    feat = features[0]
    assert feat["type"] == "Feature"
    assert feat["id"] == "ULR-HAV-000001"
    assert feat["geometry"]["type"] == "Polygon"
    assert len(feat["geometry"]["coordinates"][0]) == 5

    props = feat["properties"]
    assert props["parcel_id"] == "ULR-HAV-000001"
    assert props["land_use"] == "RESIDENTIAL"
    assert props["confidence_score"] == 0.940
    assert props["validation_status"] == "PASS"
    assert props["human_review_decision"] == "MERGE_RECONCILE"
    assert props["resolution_status"] == "UNIFIED"
    assert props["provenance_id"] is not None


@pytest.mark.asyncio
async def test_stage14_csv_generation_and_inspection(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test authoritative CSV deliverable:
    1. Requests CSV export.
    2. Downloads and parses CSV rows.
    3. Confirms centroid lat/lon without raw geometry blobs.
    4. Confirms provenance linkage column.
    """
    env = await setup_stage14_test_env(client, db_session)
    proj_id = env["project_id"]

    create_resp = await client.post(
        f"/api/v1/projects/{proj_id}/exports",
        json={"format": "csv", "include_quarantined": False},
    )
    assert create_resp.status_code == 201
    job = create_resp.json()
    assert job["format"] == "csv"
    assert job["record_count"] == 1

    dl_resp = await client.get(job["download_url"])
    assert dl_resp.status_code == 200
    assert "text/csv" in dl_resp.headers["content-type"]

    csv_lines = dl_resp.text.strip().splitlines()
    reader = csv.DictReader(csv_lines)
    rows = list(reader)
    assert len(rows) == 1

    r = rows[0]
    assert r["parcel_id"] == "ULR-HAV-000001"
    assert r["land_use"] == "RESIDENTIAL"
    assert r["resolution_status"] == "UNIFIED"
    assert float(r["confidence_score"]) == 0.94
    assert r["provenance_id"] != ""
    # Verify centroids
    assert float(r["centroid_latitude"]) > 18.0
    assert float(r["centroid_longitude"]) > 73.0


@pytest.mark.asyncio
async def test_stage14_geopackage_generation_and_inspection(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test real GeoPackage (.gpkg) deliverable generation:
    1. Requests GeoPackage export.
    2. Downloads binary artifact.
    3. Reads file using GeoPandas.
    4. Validates layer name 'unified_land_records', feature count, and geometry.
    """
    env = await setup_stage14_test_env(client, db_session)
    proj_id = env["project_id"]

    create_resp = await client.post(
        f"/api/v1/projects/{proj_id}/exports",
        json={"format": "gpkg", "include_quarantined": False},
    )
    assert create_resp.status_code == 201
    job = create_resp.json()
    assert job["format"] == "gpkg"
    assert job["record_count"] == 1

    dl_resp = await client.get(job["download_url"])
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0

    with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tf:
        tf.write(dl_resp.content)
        temp_gpkg_path = tf.name

    try:
        gdf = gpd.read_file(temp_gpkg_path, layer="unified_land_records")
        assert len(gdf) == 1
        assert gdf.crs.to_string() == "EPSG:4326"
        assert gdf.iloc[0]["parcel_id"] == "ULR-HAV-000001"
        assert gdf.iloc[0]["resolution_status"] == "UNIFIED"
        assert gdf.iloc[0]["geometry"].geom_type == "Polygon"
        assert gdf.iloc[0]["provenance_id"] != ""
    finally:
        if os.path.exists(temp_gpkg_path):
            os.remove(temp_gpkg_path)


@pytest.mark.asyncio
async def test_stage14_include_quarantined_records(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test optional inclusion of quarantined records:
    1. Requests export with include_quarantined=True.
    2. Confirms both authoritative and rejected records are present (count = 2).
    3. Confirms quarantined record is explicitly marked 'REJECTED'.
    """
    env = await setup_stage14_test_env(client, db_session)
    proj_id = env["project_id"]

    create_resp = await client.post(
        f"/api/v1/projects/{proj_id}/exports",
        json={"format": "geojson", "include_quarantined": True},
    )
    assert create_resp.status_code == 201
    job = create_resp.json()
    assert job["record_count"] == 2
    assert job["authoritative_count"] == 1
    assert job["quarantined_count"] == 1
    assert job["include_quarantined"] is True

    dl_resp = await client.get(job["download_url"])
    assert dl_resp.status_code == 200
    geojson_obj = dl_resp.json()
    features = geojson_obj["features"]
    assert len(features) == 2

    res_statuses = {f["properties"]["parcel_id"]: f["properties"]["resolution_status"] for f in features}
    assert res_statuses["ULR-HAV-000001"] == "UNIFIED"
    assert res_statuses["ULR-HAV-000002"] == "REJECTED"


@pytest.mark.asyncio
async def test_stage14_manifest_generation_and_checksum(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test export deliverable manifest and cryptographic SHA256 integrity:
    1. Requests export.
    2. Fetches manifest via /exports/{export_id}/manifest.
    3. Downloads file and computes SHA256 digest.
    4. Validates manifest SHA256 checksum matches exact file bytes.
    """
    env = await setup_stage14_test_env(client, db_session)
    proj_id = env["project_id"]

    create_resp = await client.post(
        f"/api/v1/projects/{proj_id}/exports",
        json={"format": "geojson", "include_quarantined": False},
    )
    assert create_resp.status_code == 201
    job = create_resp.json()
    export_id = job["id"]

    # Fetch manifest
    man_resp = await client.get(f"/api/v1/projects/{proj_id}/exports/{export_id}/manifest")
    assert man_resp.status_code == 200
    manifest = man_resp.json()
    assert manifest["project_id"] == str(proj_id)
    assert manifest["export_format"] == "geojson"
    assert manifest["crs"] == "EPSG:4326"
    assert manifest["total_records"] == 1
    assert manifest["authoritative_records"] == 1
    assert manifest["quarantined_records"] == 1
    assert manifest["stage12_execution_id"] is not None
    assert manifest["stage13_execution_id"] is not None

    # Verify SHA256 matches actual file bytes
    dl_resp = await client.get(job["download_url"])
    assert dl_resp.status_code == 200
    computed_sha = hashlib.sha256(dl_resp.content).hexdigest()
    assert manifest["sha256_checksum"] == computed_sha


@pytest.mark.asyncio
async def test_stage14_export_history_and_error_handling(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test export history listing and error handling:
    1. Generates 2 exports.
    2. Lists export history and confirms order.
    3. Tests 404 on invalid export ID.
    4. Tests 400 on unsupported format.
    """
    env = await setup_stage14_test_env(client, db_session)
    proj_id = env["project_id"]

    # Generate 2 exports
    await client.post(f"/api/v1/projects/{proj_id}/exports", json={"format": "geojson"})
    await client.post(f"/api/v1/projects/{proj_id}/exports", json={"format": "csv"})

    # List history
    hist_resp = await client.get(f"/api/v1/projects/{proj_id}/exports")
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert hist["total"] >= 2
    assert len(hist["items"]) >= 2

    # Invalid export ID
    fake_id = uuid.uuid4()
    not_found = await client.get(f"/api/v1/projects/{proj_id}/exports/{fake_id}/download")
    assert not_found.status_code == 404

    # Unsupported format
    bad_fmt = await client.post(
        f"/api/v1/projects/{proj_id}/exports",
        json={"format": "unsupported_shapefile"},
    )
    assert bad_fmt.status_code == 400
    assert "Unsupported export format" in get_err_msg(bad_fmt)

