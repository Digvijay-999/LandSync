# LandSync AI — Geospatial Data Harmonization Platform

LandSync AI is an AI-assisted geospatial data harmonization platform engineered to ingest, profile, match, and resolve heterogeneous land records (cadastral surveys, municipal GIS parcels, property registers, and drone-derived structures) into unified, traceable land records.

---

## 1. Architecture Overview

LandSync AI follows a clean, modular monorepo architecture:

- **Frontend**: Single-Page Application (SPA) with centralized API services, global state management, and real-time backend telemetry.
- **Backend**: FastAPI asynchronous server implementing a clean application factory, service-layer pattern (thin route handlers, domain logic in services), and structured diagnostics.
- **Database**: PostgreSQL with PostGIS extension for spatial queries, indices, and coordinate reference system (CRS) transformations.
- **Data Pipeline**: 14-stage end-to-end processing pipeline with extensible architectural hooks.

```
land-sync-ai/
├── frontend/          # React + TypeScript + Vite + Tailwind CSS + TanStack Query + Zustand
├── backend/           # FastAPI + SQLAlchemy 2.0 (async) + Alembic + Pydantic v2
├── database/init/     # PostGIS extension initializers
├── demo-data/         # Geospatial sample data directory
├── docs/              # Architectural diagrams and design specifications
├── docker-compose.yml # Container orchestration
└── .env.example       # Environment template
```

---

## 2. Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, React Router, Lucide React |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (asyncpg), Alembic, Pytest |
| **Database** | PostgreSQL 16 + PostGIS 3.4 |
| **DevOps** | Docker, Docker Compose |

---

## 3. Prerequisites

- [Docker Desktop](https://www.docker.com/) (v24+ with Compose v2+)
- *Or for native host development:*
  - Node.js (v20+) & npm
  - Python (v3.11+)
  - Local PostgreSQL 16 with PostGIS extension enabled

---

## 4. Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async connection string for FastAPI (`asyncpg`) | `postgresql+asyncpg://landsync:landsync_secret_dev_pass@postgres-postgis:5432/landsync` |
| `DATABASE_URL_SYNC` | Sync connection string for Alembic migrations | `postgresql://landsync:landsync_secret_dev_pass@postgres-postgis:5432/landsync` |
| `VITE_API_URL` | Base API URL for frontend client | `http://localhost:8000` |
| `CORS_ORIGINS` | Permitted browser origins | `["http://localhost:5173"]` |

---

## 5. Docker Quickstart (Recommended)

Start all services (Database + Backend + Frontend):

```bash
# Build and start all services in detached mode
docker compose up -d --build

# View real-time container logs
docker compose logs -f

# Verify service health
docker compose ps

# Stop containers
docker compose down
```

Access points:
- **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
- **Backend API Docs (Swagger)**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **Health Diagnostics Endpoint**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 6. Host / Local Development Commands

### Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000

# Run automated tests
pytest tests/ -v
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev

# Run production TypeScript and Vite build
npm run build
```

---

## 7. Current Implementation Status (Milestone 01: Foundation)

- [x] Monorepo structure with backend, frontend, database, docs, and demo-data directories.
- [x] PostgreSQL 16 container with PostGIS 3.4 enabled.
- [x] FastAPI application factory with structured error handling, CORS, and logging.
- [x] Database health diagnostic (`GET /api/health`) querying PostGIS version.
- [x] SQLAlchemy 2.0 async engine and Alembic migration system with initial `Project` model.
- [x] Thin API routes with decoupled service layer (`ProjectService`, `HealthService`).
- [x] Vite + React + TypeScript frontend with Tailwind CSS and dark technical design system.
- [x] Centralized API client, TanStack Query hooks, and Zustand store.
- [x] Application shell with routing (`/dashboard`, `/projects`, `/projects/:projectId`).
- [x] Docker Compose multi-container setup with healthchecks and volume persistence.

---

## 8. Planned Milestones

1. **Milestone 01 (Complete)**: Core Foundation, Dockerized PostGIS, API architecture, Frontend shell.
2. **Milestone 02**: Data Ingestion (GeoJSON, Shapefile, CSV/Parquet uploads) & Profiling.
3. **Milestone 03**: Coordinate Reference System (CRS) Normalization (PyProj/GDAL) & Schema Mapping.
4. **Milestone 04**: Spatial Candidate Generation (PostGIS spatial indexes) & Feature Matching.
5. **Milestone 05**: Geometry Harmonization & Conflict Detection.
6. **Milestone 06**: Confidence Scoring & Interactive Human Review Workflow.
7. **Milestone 07**: Unified Master Record Generation, Provenance Tracking & Export.
