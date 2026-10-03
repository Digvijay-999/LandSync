<div align="center">

# LANDSYNC AI

### AI-Powered Geospatial Data Harmonization for Creating Trusted, Traceable Unified Land Records

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4-336791.svg?style=flat&logo=postgresql)](https://postgis.net/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg?style=flat&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6.svg?style=flat&logo=typescript)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4-646CFF.svg?style=flat&logo=vite)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?style=flat&logo=docker)](https://www.docker.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-FF6F00.svg?style=flat)](https://github.com/langchain-ai/langgraph)

[Overview](#1-what-is-landsync-ai) · [The Problem](#2-the-problem) · [14-Stage Pipeline](#3-the-landsync-approach) · [AI Copilot](#6-ai-copilot) · [GIS Map](#8-gis-command-center) · [Architecture](#14-architecture) · [Quickstart](#17-quick-start)

</div>

---

## 1. What is LandSync AI?

**LandSync AI** is a geospatial data harmonization and cadastre intelligence platform. It resolves a fundamental challenge in spatial administration: land information is fragmented across disparate municipal surveys, revenue registries, cadastral departments, and drone captures—each characterized by differing schemas, projections, geometry drift, and conflicting ownership records.

Traditional GIS integration typically forces bulk overwrites or naive schema mapping, inevitably causing spatial overlaps, data loss, and unexplainable property boundaries. **LandSync AI** automates multi-signal spatial matching, flags topological and attribute conflicts, exposes explainable confidence scores, mandates human review where warranted, and synthesizes authoritative **Unified Land Records (ULR)** backed by an immutable W3C PROV-O audit trail.

> **Key Principle**: AI assists spatial reasoning and conflict investigation, but authoritative land-record decisions remain traceable, evidence-grounded, and human-reviewable.

---

## 2. The Problem

Modern land governance struggles with siloed, asynchronous records that lead to boundary disputes, tax leakage, and planning paralysis:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRAGMENTED SOURCE DATASETS                      │
├─────────────────┬───────────────────┬─────────────────┬────────────────┤
│ Cadastral Survey│ Municipal Revenue │ Drone Capture   │ Property Deeds │
│ (EPSG:32643)    │ (EPSG:4326)       │ (High-res Ortho)│ (Tabular CSV)  │
└────────┬────────┴─────────┬─────────┴────────┬────────┴────────┬───────┘
         │                  │                  │                 │
         ▼                  ▼                  ▼                 ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ • Inconsistent Schemas          • Coordinate Reference Drift         │
 │ • Slivers & Boundary Overlaps   • Attribute Discrepancies (Area/Use) │
 │ • Ambiguous Parcel Matchings    • Zero Cross-Source Provenance       │
 └──────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
                 NO SINGLE SOURCE OF DEFENSIVE TRUTH
```

---

## 3. The LandSync Approach

LandSync AI processes incoming geospatial assets through an automated, deterministic **14-Stage Harmonization Pipeline**:

```mermaid
graph LR
    S01[01 Ingestion] --> S02[02 Profiling]
    S02 --> S03[03 CRS Norm]
    S03 --> S04[04 Schema Norm]
    S04 --> S05[05 Spatial Candidates]
    S05 --> S06[06 Feature Match]
    S06 --> S07[07 Harmonization]
    S07 --> S08[08 Conflict Detection]
    S08 --> S09[09 Validation]
    S09 --> S10[10 Confidence]
    S10 --> S11[11 Human Review]
    S11 --> S12[12 Unified Record]
    S12 --> S13[13 Provenance]
    S13 --> S14[14 Export]
```

### Complete 14-Stage Workflow Breakdown

| # | Stage | Name | Purpose & Engineering Mechanism |
|---|---|---|---|
| **01** | `ingestion` | **Data Ingestion** | Ingests GeoJSON, Shapefile ZIPs, GeoPackages, and CSV coordinates with schema sanitization. |
| **02** | `profiling` | **Data Profiling** | Evaluates topological health, `ST_IsValid`, bounding extents, coordinate ranges, and area variance. |
| **03** | `crs` | **CRS Normalization** | Reprojects heterogeneous projections into unified canonical `EPSG:4326` using PyProj and PostGIS `ST_Transform`. |
| **04** | `schema` | **Schema Normalization** | Normalizes attributes into JSONB structures and assigns domain roles (`CADASTRAL`, `MUNICIPAL`, `DRONE`). |
| **05** | `candidate` | **Spatial Candidate Gen** | Leverages PostGIS GiST spatial indexing (`ST_DWithin`, `ST_Intersects`) to pair neighboring parcels within a search radius. |
| **06** | `matching` | **Feature Matching** | Evaluates multi-signal similarity: Spatial IoU overlap, Hausdorff distance, centroid proximity, and Levenshtein string matching. |
| **07** | `harmonization` | **Attr/Geom Harmonization** | Resolves geometries using semantic hierarchy (`Cadastral > Drone > Municipal`) and merges reconciled attributes. |
| **08** | `conflict` | **Conflict Detection** | Flags boundary variances exceeding tolerance thresholds, area discrepancies, and conflicting land-use classes. |
| **09** | `validation` | **Validation** | Executes topological and business rule suites: self-intersections, sliver polygons, area limits, and semantic constraints. |
| **10** | `confidence` | **Confidence Scoring** | Computes explainable, weighted composite scores [0.0–1.0] across spatial, geometric, attribute, and temporal signals. |
| **11** | `review` | **Human Review** | Prioritized adjudication queue for flagged and ambiguous parcels with side-by-side inspection and manual overrides. |
| **12** | `record` | **Unified Record** | Synthesizes master cadastre: authoritative active parcels for downstream GIS and quarantined records for unresolved items. |
| **13** | `provenance` | **Provenance** | Generates immutable W3C PROV-O audit trails detailing lineage, transformations, inputs, and operator timestamps. |
| **14** | `export` | **Export** | Generates defensible GIS deliverables in GeoJSON, GeoPackage, and CSV with SHA256 integrity checksums. |

---

## 4. Why LandSync is Different

- **Spatial + Semantic Reconciliation**: Integrates boundary geometry IoU and Hausdorff metrics with attribute-level validation rather than treating coordinates and properties as isolated problems.
- **Human-in-the-Loop Governance**: Contentious parcel disputes are never silently resolved by an algorithm; they enter a prioritized human review queue with complete context.
- **Explainable Confidence Signals**: Every match and synthesis produces component weights (spatial, geometry, attribute, temporal) with plain-language explanations.
- **Deterministic Read-Only AI**: The AI Copilot operates under a strict read-only evidence guard. Claims are grounded directly in PostGIS tables, preventing hallucinations.
- **W3C PROV-O Lineage**: Every authoritative parcel traces back through its exact source dataset, match run, review decision, and pipeline execution timestamp.
- **Defensible Exports**: All deliverables are output with cryptographic SHA256 checksum manifests for legal cadastre compliance.

---

## 5. Key Features

| Category | Capability | Technical Details |
|---|---|---|
| **Spatial Engine** | High-performance PostGIS backend | GiST indexes, `ST_Transform`, `ST_Intersection`, `ST_Area`, `ST_HausdorffDistance`, `ST_Centroid` |
| **Pipeline Automation** | Dependency-gated 14-stage workflow | Prerequisite validation, state persistence, execution tracking, idempotent re-runs |
| **Multi-Signal Matching** | Explainable parcel matching | Area discrepancy ratio, Hausdorff distance, centroid delta, boundary IoU, Levenshtein name match |
| **Conflict Detection** | Multi-type anomaly flagging | Geometric overlap, sliver detection, land-use classification dispute, mutation variance |
| **Human Review** | Adjudication workstation | Side-by-side attribute comparison, geometry preview, 4 decision actions with notes |
| **Unified Cadastre** | Master parcel synthesis | Authoritative active layer vs quarantined conflict layer with strict review precedence |
| **AI Copilot** | Multi-agent reasoning assistant | LangGraph StateGraph, vector semantic search, PostGIS query tools, 1-click demo prompt chips |
| **Deliverables** | Certified geospatial exports | Multi-format (GeoJSON, GeoPackage `.gpkg`, CSV) with SHA256 integrity verification |

---

## 6. AI Copilot

The **LandSync Evidence Assistant** is an agentic copilot engineered to investigate boundary anomalies, explain adjudication records, and summarize harmonization status without modifying database state.

```
                    User Natural Language Inquiry
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │ LangGraph Supervisor  │  (Intent Classification)
                     │     planner_node      │
                     └───────────┬───────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
   │    db_worker    │  │ spatial_worker  │  │   rag_worker    │
   │ Project Summary │  │ Proximity & IoU │  │ Semantic Vector │
   │ Unified Records │  │ Buffer & Extent │  │ Evidence Search │
   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │    synthesize_node    │  (Evidence Grounding)
                     └───────────┬───────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │     verifier_node     │  (Deterministic Score)
                     └───────────┬───────────┘
                                 │
                                 ▼
                   Grounded Response + Citations
```

### Verified Demonstration Inquiries (1-Click Chips)

The assistant UI provides interactive chips for instant, reproducible live demonstrations:

- `"How many authoritative unified records were created?"`  
  *Intent: `PROJECT_OVERVIEW`* | Evaluates live database counts: returns 30 total unified records (24 authoritative active, 6 quarantined).
- `"Explain why Parcel #104 was quarantined"`  
  *Intent: `GENERAL_GIS_QUERY`* | Queries conflict detection and adjudication tables to explain boundary discrepancy and review history.
- `"Which parcels have geometry conflicts?"`  
  *Intent: `CONFLICT_EXPLANATION`* | Lists conflicting parcels with specific area variance and overlap metrics.
- `"Show the provenance chain for ULR-PUN-HAV-0012"`  
  *Intent: `PROVENANCE_TRACE`* | Traces source datasets, candidate pairings, validation outcomes, and human review actions.

---

## 7. RAG / Knowledge Layer

The Copilot leverages a PostgreSQL-backed semantic knowledge base (`assistant_documents` table) using 384-dimensional dense vector embeddings:

- **Embeddings**: Generated for project context, dataset schemas, coordinate systems, conflict definitions, validation rules, and provenance summaries.
- **Similarity Metric**: Cosine distance search paired with metadata filtering.
- **Context Injection**: Retrieved document snippets are fed into the synthesizer node along with PostGIS query rows, ensuring complete situational awareness.

---

## 8. GIS Command Center

The main dashboard embeds a **MapLibre GL JS** interactive map workspace:

- **Unified Records Overlay**: Visualizes synthesized Stage 12 cadastral parcels directly on the map.
  - **Authoritative Records** (24): Displayed with vibrant emerald styling representing approved cadastre parcels.
  - **Quarantined Records** (6): Displayed with dashed rose/amber borders representing parcels requiring further field survey.
- **Source Layer Toggles**: Independent visibility and opacity controls for Cadastral Survey and Municipal GIS layers.
- **Spatial Tools**: Interactive parcel inspection, attribute popups, zoom-to-extent, and Fit Project Extent.
- **Copilot Integration**: Seamless trigger connecting map inspection to the AI assistant drawer.

---

## 9. Human-in-the-Loop Reconciliation

When parcels exhibit severe discrepancies or low confidence, LandSync AI routes them to **Stage 11: Human Review**:

```
                  Harmonized Discrepancy Detected
                                │
                                ▼
                   ┌─────────────────────────┐
                   │    Human Review Queue   │
                   └────────────┬────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ACCEPT_SOURCE_A│       │ACCEPT_SOURCE_B│       │MERGE_RECONCILE│
│Adopts Cadastre│       │Adopts Drone   │       │Blends Approved│
│Geometry/Attrs │       │Geometry/Attrs │       │Field Values   │
└───────┬───────┘       └───────┬───────┘       └───────┬───────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                ▼                               ▼
       Authoritative Record             REJECT_UNRESOLVED
         (Status: ACTIVE)              Quarantined Parcel
                                       (Status: CONFLICT)
```

---

## 10. Unified Land Records (Stage 12)

Stage 12 synthesizes master cadastre entities by applying strict precedence to human adjudication decisions:

- **Status Separation**:
  - `ACTIVE` (Authoritative): Reconciled, topologically sound parcels ready for legal land administration.
  - `CONFLICT` (Quarantined): Gated records with unresolved overlaps or pending legal disputes.
- **Geometry Integrity**: Enforces `ST_IsValid`, topological simplification, and single coordinate projection (`EPSG:4326`).

---

## 11. Provenance (Stage 13)

LandSync AI implements the **W3C PROV-O** data model to maintain complete auditability:

```
[Raw Source File] ──► [Canonical Feature] ──► [Feature Match]
                                                    │
[Unified Land Record] ◄── [Adjudication Decision] ◄─┴──► [Geospatial Conflict]
```

- **Lineage Completeness**: **100%** coverage across all 30 unified records.
- **Audit Logging**: **84** immutable provenance audit events recorded with execution timestamps, contributing source versions, and reviewer identities.

---

## 12. Exports (Stage 14)

Stage 14 produces standardized, verified deliverables for external GIS software:

- **Formats**:
  - **GeoJSON**: Standard web GIS format with complete property metadata.
  - **GeoPackage (`.gpkg`)**: SQLite-based open container for QGIS / ArcGIS enterprise mapping.
  - **CSV**: Tabular export containing coordinate bounds, attributes, and confidence scores.
- **Integrity Verification**: Every export file is hashed on completion and accompanied by a cryptographic **SHA256 checksum** in the database manifest.

---

## 13. Verified System State (Pune Haveli Project)

The platform includes a complete, pre-configured live demonstration workspace:

| Domain Metric | Verified Live Result |
|---|---:|
| **Target Project** | Pune Haveli Land Survey (`92534d7c-3d0f-4cbe-96af-2449f320b470`) |
| **Pipeline Completion** | **14 / 14 Stages Completed** |
| **Ingested Datasets** | 2 (`pune_haveli_demo_parcels` & `pune_haveli_municipal_survey`) |
| **Raw Source Features** | 60 |
| **Canonical Features** | 60 (`EPSG:4326`) |
| **Feature Matches Evaluated** | 210 |
| **Geospatial Conflicts Flagged** | 150 (148 open, 1 acknowledged, 1 resolved) |
| **Validation Rules Computed** | 30 |
| **Human Review Decisions** | **30 Decisions Recorded (100% queue completion)** |
| **Authoritative Records** | **24 Active Unified Land Records** |
| **Quarantined Records** | **6 Quarantined Records** |
| **Provenance Lineage Traced** | **30 / 30 Records (100% coverage, 84 audit events)** |
| **Export Deliverables** | 4 jobs (GeoJSON, GeoPackage, CSV) with SHA256 checksums |
| **Backend Test Suite** | **98 collected: 97 passed, 0 failed, 1 skipped** |
| **Frontend TypeScript Build** | **0 errors, clean production bundle** |

---

## 14. Architecture

```
                    ┌────────────────────────────────────────┐
                    │          React 18 + Vite 5 UI          │
                    │   MapLibre GL JS · Tailwind CSS        │
                    │   TanStack Query · Zustand Store       │
                    └───────────────────┬────────────────────┘
                                        │
                                REST API Calls (JSON)
                                        │
                    ┌───────────────────▼────────────────────┐
                    │             FastAPI Backend            │
                    │   Pydantic v2 · Async SQLAlchemy 2.0   │
                    │   14-Stage Domain Pipeline Engines     │
                    └───────────┬───────────────────┬────────┘
                                │                   │
              ┌─────────────────┘                   └─────────────────┐
              ▼                                                       ▼
   ┌──────────────────────┐                                ┌──────────────────────┐
   │ PostgreSQL 16        │                                │ LangGraph Assistant  │
   │ + PostGIS 3.4        │                                │ Multi-Worker Graph   │
   │ Spatial Tables       │                                │ Dense Vector RAG     │
   │ GiST Indexes         │                                │ Read-Only Verifier   │
   └──────────┬───────────┘                                └──────────┬───────────┘
              │                                                       │
              └───────────────────────────┬───────────────────────────┘
                                          ▼
                                ┌───────────────────┐
                                │   Master Output   │
                                │ • Unified Cadastre│
                                │ • PROV-O Lineage  │
                                │ • SHA256 Exports  │
                                └───────────────────┘
```

---

## 15. Technology Stack

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| **React** | `^18.3.1` | Component UI hierarchy and state rendering |
| **TypeScript** | `^5.5.3` | Static type safety and strict schema validation |
| **Vite** | `^5.4.2` | Rapid build tooling and ESM development server |
| **MapLibre GL JS** | `^4.7.1` | GPU-accelerated vector map rendering and polygon visualization |
| **Tailwind CSS** | `^3.4.10` | Responsive utility-first design system |
| **TanStack Query** | `^5.56.2` | Async server-state management and query caching |
| **Zustand** | `^4.5.5` | Lightweight client state for spatial context and UI controls |
| **Lucide React** | `^0.441.0` | Accessible, unified iconography |

### Backend & Geospatial
| Technology | Version | Purpose |
|---|---|---|
| **FastAPI** | `^0.115.0` | High-throughput asynchronous Python web framework |
| **Python** | `3.11` | Core backend runtime |
| **PostgreSQL / PostGIS** | `16 / 3.4` | Spatial relational database with native GiST indexing |
| **SQLAlchemy (Async)** | `^2.0.32` | Asynchronous ORM utilizing `asyncpg` |
| **Alembic** | `^1.13.2` | Database migration management |
| **GeoPandas & Shapely** | `^1.0.0 / ^2.0.0` | In-memory spatial manipulation, overlay, and Hausdorff metrics |
| **PyProj & Pyogrio** | `^3.6.0 / ^0.9.0` | High-performance cartographic projection and I/O drivers |
| **GeoAlchemy2** | `^0.14.0` | PostGIS spatial column integration for SQLAlchemy |

### AI & Agentic Orchestration
| Technology | Purpose |
|---|---|
| **LangGraph** | Multi-worker StateGraph orchestration (`planner`, `workers`, `synthesizer`, `verifier`) |
| **Dense Vector RAG** | PostgreSQL-backed semantic search with 384-dimensional embeddings |
| **Deterministic Reasoning** | Rule-grounded fallback ensuring 100% auditability without third-party LLM dependency |

---

## 16. Project Structure

```
landsync/
├── backend/
│   ├── alembic/                 # Database migrations (0001 through 0017)
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST endpoints (pipeline, unified, assistant, export, etc.)
│   │   ├── core/                # Configuration, logging, database session engine
│   │   ├── models/              # SQLAlchemy spatial & domain models
│   │   ├── schemas/             # Pydantic validation schemas
│   │   └── services/            # Core business logic for all 14 stages + AI assistant
│   │       ├── assistant/       # LangGraph orchestrator, RAG vector store, tools
│   │       ├── matching/        # Spatial candidate & multi-signal matching
│   │       ├── conflict/        # Geospatial anomaly & variance detection
│   │       ├── validation/      # Topological and semantic rule checkers
│   │       ├── adjudication/    # Human review workflow engine
│   │       ├── unified/         # Master cadastre synthesis service
│   │       ├── provenance/      # W3C PROV-O audit trail manager
│   │       └── export/          # GeoJSON, GeoPackage, and CSV generators
│   ├── scripts/                 # Live inspection and diagnostic scripts
│   ├── tests/                   # Pytest test suite (98 test cases)
│   └── requirements.txt         # Pinned Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── assistant/       # AI Copilot drawer and demo prompt chips
│   │   │   ├── map/             # MapLibre canvas and Unified Records layer overlay
│   │   │   ├── pipeline/        # 14-stage interactive pipeline panel
│   │   │   └── unified/         # Unified records explorer and table
│   │   ├── hooks/               # TanStack query and mutation hooks
│   │   ├── pages/               # Dashboard, Project Detail, Reconciliation
│   │   └── stores/              # Zustand state stores
│   ├── package.json             # Pinned Node dependencies
│   └── vite.config.ts           # Vite build configuration
├── database/init/               # PostGIS initialization SQL scripts
├── demo-data/                   # Sample cadastral, municipal, and drone datasets
├── docker-compose.yml           # Multi-container orchestration definition
├── .env.example                 # Environment configuration template
└── README.md                    # Project documentation
```

---

## 17. Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v24+ with Docker Compose v2+) running on Windows, macOS, or Linux.
- [Git](https://git-scm.com/)

### Step-by-Step Launch

```bash
# 1. Clone the repository
git clone https://github.com/Digvijay-999/LandSync.git
cd LandSync

# 2. Copy the environment configuration template
cp .env.example .env
# (On Windows PowerShell: Copy-Item .env.example .env)

# 3. Start all services via Docker Compose
docker compose up --build
```

### Access Points

| Component | URL | Description |
|---|---|---|
| **Web Dashboard** | [http://localhost:5173](http://localhost:5173) | Interactive frontend workspace and map |
| **API Documentation (Swagger)** | [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs) | Interactive OpenAPI REST documentation |
| **API Documentation (ReDoc)** | [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc) | Alternative formatted API reference |
| **Health Endpoint** | [http://localhost:8000/api/health](http://localhost:8000/api/health) | PostGIS version and database connectivity diagnostic |

---

## 18. Environment Variables

Configure application settings in `.env` at the repository root:

| Variable | Description | Required | Default |
|---|---|---|---|
| `ENVIRONMENT` | Runtime mode (`development` / `production`) | No | `development` |
| `DEBUG` | Enable verbose debugging and stack traces | No | `true` |
| `LOG_LEVEL` | Logging threshold (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | No | `INFO` |
| `POSTGRES_SERVER` | PostgreSQL hostname | Yes | `postgres-postgis` |
| `POSTGRES_PORT` | PostgreSQL port | Yes | `5432` |
| `POSTGRES_DB` | Database name | Yes | `landsync` |
| `POSTGRES_USER` | Database username | Yes | `landsync` |
| `POSTGRES_PASSWORD` | Database password | Yes | `landsync_secret_dev_pass` |
| `DATABASE_URL` | Async connection string for FastAPI (`asyncpg`) | Yes | *Constructed from POSTGRES credentials* |
| `DATABASE_URL_SYNC`| Sync connection string for Alembic migrations | Yes | *Constructed from POSTGRES credentials* |
| `VITE_API_URL` | Backend URL consumed by the React client | Yes | `http://localhost:8000` |
| `AI_ENABLED` | Toggle AI Copilot and RAG features | No | `true` |
| `AI_PROVIDER` | LLM reasoning provider (`auto`, `deterministic`, `openai`) | No | `auto` |
| `OPENAI_API_KEY` | Optional key for external OpenAI model invocation | No | *None (falls back to deterministic engine)* |

---

## 19. Verification & Testing

### Running Backend Tests
Execute the complete test suite inside the running backend container:
```bash
docker exec landsync-backend pytest -v
```
**Verified Result**: `97 passed, 1 skipped, 0 failed in 52.66s` (covering ingestion, PostGIS queries, matching, conflict detection, validation, confidence scoring, adjudication, unified record synthesis, provenance, and exports).

### Running Frontend Checks
```bash
cd frontend

# Verify TypeScript types
npx tsc --noEmit

# Test production compilation
npm run build
```
**Verified Result**: `0 TypeScript errors`, successful Vite build in `<15s`.

---

## 20. Demo Walkthrough (2-Minute Sequence)

1. **Open Workspace**: Navigate to [http://localhost:5173](http://localhost:5173) and select the **Pune Haveli Land Survey** project.
2. **Inspect Main Map**: View the **Interactive Map Workspace** with Cadastral and Municipal vector layers rendered.
3. **Toggle Unified Records Overlay**: Click the **Unified Records (30)** layer toggle on the map. Notice the **24 Authoritative** parcels highlighted in emerald and **6 Quarantined** parcels highlighted in dashed rose/amber.
4. **Examine 14-Stage Pipeline**: Switch to the **Pipeline & Harmonization** tab. Observe all 14 stages marked `completed`. Click **Stage 11 (Human Review)** to see the 30 recorded adjudication decisions.
5. **Ask AI Copilot**: Click the **Ask AI** button in the header. Click the chip: *"How many authoritative unified records were created?"* Observe the real-time grounded database synthesis reporting 24 authoritative and 6 quarantined records with evidence citations.
6. **Verify Provenance & Lineage**: Click **Stage 13 (Provenance)** to view 100% lineage completeness across 84 audit events.
7. **Download Deliverables**: Click **Stage 14 (Export)** to review generated GeoJSON, GeoPackage, and CSV files complete with SHA256 integrity checksums.

---

## 21. Current Prototype Scope & Production Hardening

To maintain transparency, the following items represent intentional boundary constraints for the current demonstration release:

- **Authentication & RBAC**: Currently operates in an open single-tenant mode without JWT or role-based permission tiers.
- **Asynchronous Task Workers**: Pipeline executions run directly via FastAPI background tasks; enterprise deployments exceeding 100,000 parcels would benefit from distributed Celery/Redis workers.
- **Vector Storage**: Currently utilizes PostgreSQL-backed embeddings; high-volume production deployments can scale to specialized pgvector partitions or managed vector indexes.
- **Blob Storage**: Export artifacts are saved to local volume storage rather than AWS S3 or Google Cloud Storage buckets.

---

## 22. Roadmap

- [x] Full 14-stage automated geospatial data reconciliation pipeline
- [x] Multi-signal explainable spatial feature matching (IoU, Hausdorff, Levenshtein)
- [x] Topological validation and geometric anomaly conflict detection
- [x] Human-in-the-loop adjudication workstation with 4 distinct decision pathways
- [x] Authoritative Unified Land Record (ULR) master cadastre synthesis
- [x] W3C PROV-O audit trail and lineage reconstruction
- [x] Multi-format certified export generation (GeoJSON, GeoPackage, CSV) with SHA256 checksums
- [x] MapLibre GL JS interactive command center with Unified Records layer overlay
- [x] Agentic AI Copilot (LangGraph StateGraph + dense vector RAG + 100% read-only evidence guard)
- [ ] Enterprise JWT Authentication & Role-Based Access Control (RBAC)
- [ ] Distributed Celery/Redis asynchronous job queue for large-scale municipal datasets
- [ ] Bulk multi-select batch adjudication actions in human review
- [ ] Cloud object storage drivers (AWS S3 / GCS)
- [ ] Automated cadastral survey certificate generation in PDF/SVG

---

## 23. Engineering Highlights

- **Why PostGIS?** Geospatial precision cannot be achieved through Euclidean approximations. PostGIS provides exact geodesic reprojection, spherical distances, and native R-Tree spatial indexing (`GiST`).
- **Why Human Review Precedence?** Land ownership has severe legal and financial ramifications. An algorithm should never silently rewrite a disputed boundary; LandSync guarantees that human review decisions explicitly override automated assumptions.
- **Why Read-Only AI Grounding?** LLMs are prone to hallucinating plausible spatial coordinates. LandSync isolates the AI Copilot to a read-only observer that retrieves and synthesizes facts directly from database rows, enforcing zero autonomous data modification.
- **Why SHA256 Checksums?** Cadastral files are legal instruments. Export manifests guarantee that spatial datasets delivered to external planning authorities have not been altered or corrupted in transit.

---

## 24. License

This project is licensed under the **Apache 2.0 License**.
