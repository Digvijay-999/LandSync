# LandSync AI — System Architecture & Design

LandSync AI is an AI-assisted geospatial data harmonization platform designed to combine heterogeneous land/geospatial datasets (cadastral, municipal GIS, revenue/property, and drone-derived survey data) into unified, traceable land records.

---

## 1. Core Architectural Principles

1. **Thin Route Handlers**: FastAPI endpoints validate inputs via Pydantic and delegate execution immediately to service layers.
2. **Business Logic in Services**: All domain logic, database operations, and future geospatial orchestration reside in dedicated service modules.
3. **Strict Separation of Models and Schemas**:
   - SQLAlchemy models represent persistent database tables.
   - Pydantic schemas define API request/response contracts and validation rules.
4. **Geospatial Isolation**: Geospatial transformation algorithms will never execute directly inside HTTP route handlers. They belong in dedicated geospatial processing services.
5. **Clean Extension Points**: Future pipeline phases are represented as architectural hooks/extension points rather than mock or fake implementations.
6. **Centralized Frontend Client**: React application consumes the backend via a centralized, typed Axios/Fetch service layer.
7. **Monolithic Modularity**: Single clean codebase without microservice overhead or distributed queue baggage during the prototyping phase.

---

## 2. Eventual Processing Pipeline

```
DATA INGESTION
   ↓
DATA PROFILING
   ↓
CRS NORMALIZATION
   ↓
SCHEMA NORMALIZATION
   ↓
SPATIAL CANDIDATE GENERATION
   ↓
FEATURE MATCHING
   ↓
ATTRIBUTE/GEOMETRY HARMONIZATION
   ↓
CONFLICT DETECTION
   ↓
VALIDATION
   ↓
CONFIDENCE SCORING
   ↓
HUMAN REVIEW
   ↓
UNIFIED RECORD
   ↓
PROVENANCE
   ↓
EXPORT
```

---

## 3. Technology Stack

- **Frontend**: React 18+, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand, React Router, Lucide React (MapLibre GL JS in subsequent milestones).
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic.
- **Database**: PostgreSQL 16 with PostGIS extension.
- **Infrastructure**: Docker and Docker Compose.
