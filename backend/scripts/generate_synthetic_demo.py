"""
Synthetic Geospatial Dataset Generator for LandSync AI Milestone 3
Generates deterministic, controlled synthetic datasets for reconciliation demo and testing:
1. Cadastral Parcels (GeoJSON Polygons) - 80 features
2. Municipal Records (CSV Points) - 75 features
3. Drone Footprints (GeoJSON Polygons) - 75 features

All datasets use a fixed random seed (42) for 100% reproducible results.
Features are distributed across all 4 classification categories:
- MATCHED (High spatial alignment & corroborating attributes)
- POSSIBLE_MATCH (Moderate overlap or slight boundary offset)
- CONFLICT (Strong spatial co-location with contradictory attributes or area)
- UNMATCHED (Features with no spatial counterpart in other datasets)

LABELED AS SYNTHETIC / DEMO DATA ONLY.
"""

import json
import csv
import random
from pathlib import Path


def generate_synthetic_datasets(output_dir: Path, base_lon: float = 73.8500, base_lat: float = 18.5200):
    output_dir.mkdir(parents=True, exist_ok=True)
    random.seed(42)

    # 1. Generate 80 Cadastral Parcels (8x10 Grid)
    cadastral_features = []
    parcel_width = 0.0008   # ~85 meters
    parcel_height = 0.0006  # ~65 meters
    gap = 0.00015           # road / path gap

    parcels_meta = []
    owners = [
        "Ramesh Sharma", "Priya Patel", "Anil Kulkarni", "Sunita Deshmukh",
        "Vikram Joshi", "Meera Nair", "Rajesh Gupta", "Kavita Rao",
        "Suresh Patil", "Neha Verma", "Deepak Shinde", "Pooja Mehta",
    ]
    uses = ["Residential", "Commercial", "Mixed Use", "Civic", "Institutional"]

    idx = 0
    for row in range(8):
        for col in range(10):
            idx += 1
            pid = f"CP-{1000 + idx}"
            x1 = base_lon + col * (parcel_width + gap)
            y1 = base_lat + row * (parcel_height + gap)
            if idx > 76:
                # Isolated rural cadastral parcels (300m gap from urban grid to demonstrate UNMATCHED no-candidate behavior)
                y1 += 0.003

            x2 = x1 + parcel_width
            y2 = y1 + parcel_height

            owner = owners[(row * 10 + col) % len(owners)]
            land_use = uses[(row + col) % len(uses)]
            area_sqm = round(parcel_width * 111000 * parcel_height * 111000 * 0.95, 1)

            poly_coords = [
                [[round(x1, 6), round(y1, 6)],
                 [round(x2, 6), round(y1, 6)],
                 [round(x2, 6), round(y2, 6)],
                 [round(x1, 6), round(y2, 6)],
                 [round(x1, 6), round(y1, 6)]]
            ]

            feature = {
                "type": "Feature",
                "properties": {
                    "parcel_id": pid,
                    "owner_name": owner,
                    "land_use": land_use,
                    "area_sqm": area_sqm,
                    "source": "SYNTHETIC_CADASTRAL_REGISTER",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": poly_coords,
                }
            }
            cadastral_features.append(feature)
            parcels_meta.append({
                "index": idx,
                "parcel_id": pid,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "cx": (x1 + x2) / 2.0, "cy": (y1 + y2) / 2.0,
                "owner": owner,
                "land_use": land_use,
                "area_sqm": area_sqm,
            })

    cadastral_geojson = {
        "type": "FeatureCollection",
        "name": "cadastral_parcels_synthetic",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": cadastral_features,
    }

    with open(output_dir / "cadastral_parcels_synth.geojson", "w", encoding="utf-8") as f:
        json.dump(cadastral_geojson, f, indent=2)

    # 2. Generate Drone Footprints (75 Polygons)
    # - 0 to 52 (53): MATCHED (conforming footprint inside parcel with aligned building_id & owner)
    # - 53 to 62 (10): POSSIBLE_MATCH (slight shift 5-10m, partial overlap)
    # - 63 to 68 (6): CONFLICT (high spatial overlap, but contradictory owner/ID)
    # - 69 to 74 (6): UNMATCHED (built in empty terrain to east, far from cadastral grid)
    # - 75 to 76 (2): AMBIGUOUS (twin symmetrical structures on parcels 40 & 41 with identical confidence)
    drone_features = []

    for d_idx in range(77):
        did = f"DRN-{2000 + d_idx + 1}"

        if d_idx == 40 or d_idx == 41:
            # Shift slightly to west (-4m) with conforming area
            p = parcels_meta[d_idx]
            bx1 = p["cx"] - 0.00004 - parcel_width * 0.42
            bx2 = p["cx"] - 0.00004 + parcel_width * 0.42
            by1 = p["cy"] - parcel_height * 0.42
            by2 = p["cy"] + parcel_height * 0.42
            prop_id = p["parcel_id"]
            owner = p["owner"]
            cls_type = p["land_use"]
        elif d_idx < 53:
            # MATCHED: Centered building footprint inside cadastral parcel
            p = parcels_meta[d_idx]
            bx1 = p["cx"] - parcel_width * 0.35
            bx2 = p["cx"] + parcel_width * 0.35
            by1 = p["cy"] - parcel_height * 0.35
            by2 = p["cy"] + parcel_height * 0.35
            prop_id = p["parcel_id"]
            owner = p["owner"]
            cls_type = p["land_use"]
        elif d_idx < 63:
            # POSSIBLE_MATCH: Slightly shifted footprint (~10m) overlapping ~60%
            p = parcels_meta[d_idx]
            shift_x = parcel_width * 0.18
            shift_y = parcel_height * 0.15
            bx1 = p["cx"] + shift_x - parcel_width * 0.38
            bx2 = p["cx"] + shift_x + parcel_width * 0.38
            by1 = p["cy"] + shift_y - parcel_height * 0.38
            by2 = p["cy"] + shift_y + parcel_height * 0.38
            prop_id = p["parcel_id"]
            owner = p["owner"]
            cls_type = p["land_use"]
        elif d_idx < 69:
            # CONFLICT: High spatial overlap, but intentionally contradictory owner and building_id
            p = parcels_meta[d_idx]
            bx1 = p["cx"] - parcel_width * 0.35
            bx2 = p["cx"] + parcel_width * 0.35
            by1 = p["cy"] - parcel_height * 0.35
            by2 = p["cy"] + parcel_height * 0.35
            prop_id = f"DISPUTED-UNKNOWN-{d_idx}"
            owner = "UNAUTHORIZED OCCUPANT / SQUATTER CORP"
            cls_type = "Commercial Warehouse"
        elif d_idx < 75:
            # UNMATCHED: Placed far outside cadastral grid (lon + 0.06 deg)
            bx1 = base_lon + 0.06 + (d_idx - 69) * 0.002
            by1 = base_lat + 0.06 + (d_idx - 69) * 0.002
            bx2 = bx1 + parcel_width * 0.5
            by2 = by1 + parcel_height * 0.5
            prop_id = f"OFFGRID-{d_idx}"
            owner = "Isolated Remote Asset"
            cls_type = "Telecom Facility"
        else:
            # AMBIGUOUS: Twin symmetrical structure on parcel 40 / 41 shifted slightly to east (+4m)
            target_p_idx = 40 if d_idx == 75 else 41
            p = parcels_meta[target_p_idx]
            bx1 = p["cx"] + 0.00004 - parcel_width * 0.42
            bx2 = p["cx"] + 0.00004 + parcel_width * 0.42
            by1 = p["cy"] - parcel_height * 0.42
            by2 = p["cy"] + parcel_height * 0.42
            prop_id = p["parcel_id"]
            owner = p["owner"]
            cls_type = p["land_use"]

        coords = [
            [[round(bx1, 6), round(by1, 6)],
             [round(bx2, 6), round(by1, 6)],
             [round(bx2, 6), round(by2, 6)],
             [round(bx1, 6), round(by2, 6)],
             [round(bx1, 6), round(by1, 6)]]
        ]
        calc_area = round(abs(bx2 - bx1) * 111000 * abs(by2 - by1) * 111000, 1)

        drone_features.append({
            "type": "Feature",
            "properties": {
                "structure_id": did,
                "parcel_ref": prop_id,
                "structure_name": f"{owner} Structure",
                "structure_type": cls_type,
                "footprint_area_sqm": calc_area,
                "survey_method": "DRONE_LIDAR_ORTHO",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": coords,
            }
        })

    drone_geojson = {
        "type": "FeatureCollection",
        "name": "drone_structures_synthetic",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": drone_features,
    }

    with open(output_dir / "drone_structures_synth.geojson", "w", encoding="utf-8") as f:
        json.dump(drone_geojson, f, indent=2)

    # 3. Generate Municipal Records (75 CSV Point records)
    # Controlled distribution:
    # - 0 to 52 (53): Point inside parcel with matching property_id & facility_name
    # - 53 to 62 (10): Point near parcel boundary with slight offset (~10m)
    # - 63 to 68 (6): CONFLICT (point inside parcel but conflicting ownership/ID)
    # - 69 to 74 (6): UNMATCHED (isolated road utility / water station far from parcels)
    municipal_rows = []
    fieldnames = [
        "asset_id", "property_id", "facility_name", "facility_type",
        "latitude", "longitude", "tax_status", "inspection_date"
    ]

    for m_idx in range(75):
        aid = f"MUN-3000{m_idx + 1:02d}"

        if m_idx == 40 or m_idx == 41:
            # Placed far offgrid to allow twin drone structures on parcels 40 & 41 to compete for rank 1
            lon = base_lon - 0.06 - (m_idx - 40) * 0.005
            lat = base_lat - 0.06 - (m_idx - 40) * 0.005
            pid = f"OFFGRID-MUNI-{m_idx}"
            name = f"Distant Substation Meter {m_idx}"
            ftype = "Electrical Infrastructure"
            tax_stat = "Municipal Asset"
        elif m_idx < 53:
            p = parcels_meta[m_idx]
            lon = p["cx"] + random.uniform(-0.0001, 0.0001)
            lat = p["cy"] + random.uniform(-0.0001, 0.0001)
            pid = p["parcel_id"]
            name = f"{p['owner']} Property"
            ftype = p["land_use"]
            tax_stat = "Tax Compliant"
        elif m_idx < 63:
            p = parcels_meta[m_idx]
            # Near boundary edge inside parcel
            lon = p["cx"] + parcel_width * 0.35
            lat = p["cy"] + parcel_height * 0.30
            pid = p["parcel_id"]
            name = f"{p['owner']} Ancillary Meter"
            ftype = "Utility Connection"
            tax_stat = "Pending Audit"
        elif m_idx < 69:
            p = parcels_meta[m_idx]
            lon = p["cx"]
            lat = p["cy"]
            pid = f"MUNICIPAL-CLAIM-ERR-{m_idx}"
            name = "Government Easement Right-of-Way"
            ftype = "Disputed Municipal Reserve"
            tax_stat = "Exempt / In Litigation"
        else:
            lon = base_lon - 0.06 - (m_idx - 69) * 0.002
            lat = base_lat - 0.06 - (m_idx - 69) * 0.002
            pid = f"OFFGRID-ASSET-{m_idx}"
            name = "Suburban Water Reservoir Tank"
            ftype = "Public Infrastructure"
            tax_stat = "Government Owned"

        municipal_rows.append({
            "asset_id": aid,
            "property_id": pid,
            "facility_name": name,
            "facility_type": ftype,
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "tax_status": tax_stat,
            "inspection_date": "2026-03-15",
        })

    with open(output_dir / "municipal_records_synth.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(municipal_rows)

    print(f"Generated synthetic demo datasets in {output_dir}:")
    print(f" - cadastral_parcels_synth.geojson ({len(cadastral_features)} polygons)")
    print(f" - drone_structures_synth.geojson ({len(drone_features)} polygons)")
    print(f" - municipal_records_synth.csv ({len(municipal_rows)} points)")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent.parent / "demo-data" / "synthetic"
    generate_synthetic_datasets(out)
