# LandSync AI — Geospatial Data Harmonization Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4-336791.svg?style=flat&logo=postgresql)](https://postgis.net/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?style=flat&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6.svg?style=flat&logo=typescript)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4-646CFF.svg?style=flat&logo=vite)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?style=flat&logo=docker)](https://www.docker.com/)

**LandSync AI** is an enterprise-grade geospatial harmonization platform engineered to ingest, profile, normalize, match, and reconcile heterogeneous land records (cadastral surveys, municipal GIS parcels, property registers, and drone-derived structures) into unified, traceable master land records.

---

## Table of Contents

1. [Quickstart — How to Start the App (Recommended)](#1-quickstart--how-to-start-the-app-recommended)
2. [Access Points & URLs](#2-access-points--urls)
3. [Architecture & 14-Stage Pipeline](#3-architecture--14-stage-pipeline)
4. [Interactive Walkthrough & Demo Guide](#4-interactive-walkthrough--demo-guide)
5. [Local / Host Development (Without Full Docker)](#5-local--host-development-without-full-docker)
6. [Testing & Validation](#6-testing--validation)
7. [Environment Configuration](#7-environment-configuration)
8. [Troubleshooting & FAQs](#8-troubleshooting--faqs)

---

## 1. Quickstart — How to Start the App (Recommended)

The fastest and most reliable way to run LandSync AI is using **Docker Compose**. It automatically starts PostgreSQL 16 with PostGIS 3.4, runs all database migrations, launches the FastAPI asynchronous backend, and starts the Vite React frontend.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v24+ with Docker Compose v2+) running on Windows, macOS, or Linux.
- Git

### Step-by-Step Start Instructions

#### 1. Clone the repository and navigate into the workspace
```bash
git clone https://github.com/Digvijay-999/LandSync.git
cd LandSync
```

#### 2. Configure Environment (One-time setup)
If `.env` does not exist, copy the template:
```bash
cp .env.example .env
```
*(On Windows PowerShell: `Copy-Item .env.example .env`)*

#### 3. Start All Services
Launch the database, backend, and frontend containers in detached mode:
```bash
docker compose up -d --build
```

#### 4. Verify Services are Healthy
```bash
docker compose ps
```
You should see all three containers running and healthy:
- `landsync-db` (Port `5432` — PostGIS 3.4)
- `landsync-backend` (Port `8000` — FastAPI)
- `landsync-frontend` (Port `5173` — React Vite)

#### 5. Stop the Application
To stop all running services:
```bash
docker compose down
```
To stop and clean database volumes (reset state):
```bash
docker compose down -v
```

---

## 2. Access Points & URLs

Once started, access the application through the following URLs:

| Service | URL | Description |
|---|---|---|
| **Frontend Web App** | [http://localhost:5173](http://localhost:5173) | Interactive geospatial dashboard, map layer inspector, and harmonization workspace |
| **Backend API Docs** | [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs) | Interactive Swagger UI for all REST endpoints |
| **Alternative Docs (ReDoc)** | [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc) | Clean ReDoc API reference |
| **Health Diagnostics** | [http://localhost:8000/api/health](http://localhost:8000/api/health) | Real-time database and PostGIS version diagnostics |
| **PostgreSQL / PostGIS** | `localhost:5432` | Database: `landsync`, User: `landsync`, Pass: `landsync_secret_dev_pass` |

---

## 3. Architecture & 14-Stage Pipeline

LandSync AI implements a structured 14-stage geospatial data reconciliation pipeline:

```
[01 Data Ingestion] ────────► [02 Data Profiling] ───────► [03 CRS Normalization]
                                                                    │
[06 Feature Matching] ◄────── [05 Spatial Candidate Gen] ◄── [04 Schema Normalization]
        │
        ▼
[07 Attr/Geom Harmonization] ─► [08 Conflict Detection] ───► [09 Validation]
                                                                    │
[12 Unified Record] ◄──────── [11 Human Review] ◄──────── [10 Confidence Scoring]
        │
        ▼
[13 Provenance] ────────────► [14 Export (GeoJSON/CSV)]
```

### Operational Stage Breakdown

| Stage | Name | Status | Key Mechanism |
|---|---|---|---|
| **01** | **Data Ingestion** | ✅ Active | Heterogeneous vector ingestion (GeoJSON, Shapefile ZIP, GeoPackage, CSV + Lat/Lon) with automatic coordinate extraction. |
| **02** | **Data Profiling** | ✅ Active | Topological validation (`ST_IsValid`), area distributions, bounding boxes, coordinate sanity checks. |
| **03** | **CRS Normalization** | ✅ Active | Reprojection of all incoming vector data into canonical EPSG:4326 using PyProj and PostGIS `ST_Transform`. |
| **04** | **Schema Normalization** | ✅ Active | Sanitization into canonical JSONB structures; automatic domain role detection (`CADASTRAL`, `MUNICIPAL`, `DRONE`). |
| **05** | **Spatial Candidate Gen** | ✅ Active | PostGIS spatial index query pairing parcel candidates within distance radius via `ST_Intersects`, `ST_Contains`, and `ST_DWithin`. |
| **06** | **Feature Matching** | ✅ Active | Multi-signal explainable scoring: Spatial IoU overlap, Hausdorff boundary distance, centroid proximity, area discrepancy, and attribute Levenshtein similarity. |
| **07** | **Attribute/Geometry Harmonization** | ✅ Active | Authoritative geometry selection via semantic hierarchy (`Cadastral > Drone > Municipal`); domain attribute reconciliation (land use, mutation, risk, area); conflict detection forwarding. |
| **08** | **Conflict Detection** | 🔒 Stage 07 Dependent | Flags boundary variances, land use disagreements, and tax/mutation mismatches across sources. |
| **09** | **Validation** | 🔒 Pipeline | Topological business rule verification, slip-polygon detection, overlap checks. |
| **10** | **Confidence Scoring** | 🔒 Pipeline | Multi-component explainable scoring model with breakdown badges. |
| **11** | **Human Review** | 🔒 Pipeline | Side-by-side inspection queue for ambiguous matches and parcel boundary variances. |
| **12** | **Unified Record** | 🔒 Pipeline | Synthesis of authoritative Unified Land Records (ULR) with master geometry. |
| **13** | **Provenance** | 🔒 Pipeline | Complete lineage, source attribution, transformation timestamps, and audit event logs. |
| **14** | **Export** | 🔒 Pipeline | Export harmonized parcel layers to standard GeoJSON and CSV formats. |

---

## 4. Interactive Walkthrough & Demo Guide

Follow these steps to run a live demonstration of the LandSync platform:

1. **Open the Dashboard**:
   - Navigate to [http://localhost:5173](http://localhost:5173) in your browser.
   - Click on the **Pune Haveli Land Survey** project workspace.

2. **Inspect Spatial Layers on the Interactive Map**:
   - On the **Interactive Map** tab, inspect the two ingested geospatial layers:
     - `pune_haveli_demo_parcels` (Cadastral survey parcels, 30 features)
     - `pune_haveli_municipal_survey` (Municipal GIS linework, 30 features)
   - Toggle layers on and off, switch to satellite basemaps, or inspect individual parcels with click-to-identify popup properties.

3. **Open Pipeline & Harmonization**:
   - Click the **Pipeline Stages** tab. You will see the 14-stage workflow indicator.
   - Click on **Stage 05: Spatial Candidate Gen**:
     - Adjust the spatial search radius (e.g., 50 meters).
     - Click **Run Spatial Candidate Gen** to generate candidate parcel pairs using PostGIS spatial indexing.
   - Click on **Stage 06: Feature Matching**:
     - Adjust matching thresholds.
     - Click **Run Feature Matching** to evaluate multi-signal scores across candidates.
   - Click on **Stage 07: Attribute/Geometry Harmonization**:
     - Notice Stage 07 is **Ready to Run** and Stage 08 is locked.
     - Adjust the Area Variance Tolerance slider (default 5.0%).
     - Click **Run Attribute/Geometry Harmonization**.
     - Observe real-time execution: Stage 07 completes, displaying 30 harmonized records, authoritative geometry selection, reconciled land use, mutations, and risk ratings.
     - Notice **Stage 08: Conflict Detection** automatically unlocks and becomes **Ready**.

4. **Ask the Geospatial AI Assistant**:
   - Open the **LandSync Assistant** drawer (right side of the header).
   - Ask: *"Provide an executive overview of this LandSync project and harmonization status."* or *"What are the biggest area discrepancies between cadastral and municipal parcels?"*

---

## 5. Local / Host Development (Without Full Docker)

If you prefer developing natively with hot-reloading outside of Docker containers:

### 1. Database (Docker PostGIS)
You can still use Docker just for the PostGIS database:
```bash
docker compose up -d postgres-postgis
```

### 2. Backend (FastAPI)
```bash
cd backend

# Create and activate Python virtual environment
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start development server with reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend (React + Vite)
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite dev server
npm run dev
```

The frontend will run at [http://localhost:5173](http://localhost:5173) and proxy API requests to `http://localhost:8000`.

---

## 6. Testing & Validation

### Run Backend Tests (Pytest)

Run the backend test suite inside Docker:
```bash
docker compose exec backend pytest
```
*Or locally in the backend virtualenv: `pytest`*

Test results verify:
- Ingestion parser robustness (GeoJSON, CSV, Shapefiles)
- PostGIS spatial indexing and candidate generation
- Multi-signal feature matching algorithms
- Attribute & geometry harmonization logic
- Stage 08 lock dependency gating
- Health diagnostic endpoints

### Run Frontend Typecheck & Build

```bash
cd frontend
npm run build
```
Runs TypeScript static checking (`tsc`) followed by Vite production bundling.

---

## 7. Environment Configuration

All environment variables can be configured in `.env`:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async connection string for FastAPI (`asyncpg`) | `postgresql+asyncpg://landsync:landsync_secret_dev_pass@postgres-postgis:5432/landsync` |
| `DATABASE_URL_SYNC` | Sync connection string for Alembic migrations | `postgresql://landsync:landsync_secret_dev_pass@postgres-postgis:5432/landsync` |
| `VITE_API_URL` | Base API URL consumed by the frontend client | `http://localhost:8000` |
| `CORS_ORIGINS` | Allowed CORS origins for browser security | `["http://localhost:5173", "http://localhost:3000"]` |
| `ENVIRONMENT` | Runtime environment (`development` / `production`) | `development` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

---

## 8. Troubleshooting & FAQs

### 1. Database Connection Fails / Container Unhealthy
Ensure Docker Desktop is running and that port `5432` is not already occupied by a local PostgreSQL installation.
```bash
# Check container logs
docker compose logs postgres-postgis

# Restart the database container
docker compose restart postgres-postgis
```

### 2. PostGIS Extension Missing
Verify PostGIS is installed and recognized:
```bash
curl http://localhost:8000/api/health
```
The JSON response should report `"postgis_installed": true` and provide the PostGIS version string.

### 3. Migrations Fail on Fresh Database
Ensure database container is completely healthy before running Alembic:
```bash
docker compose exec backend alembic upgrade head
```

### 4. Port Conflicts (5173, 8000, 5432)
If another application is using port 5173 or 8000, change the host port mapping in [docker-compose.yml](file:///d:/Projects/landsync/docker-compose.yml):
```yaml
ports:
  - "8001:8000"  # Backend
  - "3000:5173"  # Frontend
```

---

## License

This project is licensed under the Apache 2.0 License.
