# Geospatial File Measurement API

A production-quality Python backend service built with FastAPI, GeoPandas, Shapely 2.x, and PyProj. The service accepts geospatial files (`.zip` Shapefiles or `.kml`), safely parses and validates the features, projects geometries into spatial reference systems (UTM), and returns area or length measurements in metric units.

---

## 1. Setup & Installation

### Prerequisites
- Python 3.10 or higher
- `pip` package manager

### Environment Setup
1. Clone or extract the project repository:
   ```bash
   cd "Geospatial File Measurement API"
   ```

2. Create and activate a Python virtual environment:
   - **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\activate
     ```

3. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application
Start the Uvicorn development server:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- **Interactive OpenAPI (Swagger) Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Running Tests
Run the test suite using `pytest`:
```bash
pytest -v
```

---

## 2. API Endpoint Documentation

### 1. `POST /api/files/`
Upload a `.zip` (Shapefile archive) or `.kml` file for processing and feature extraction.

#### Request
- **Content-Type**: `multipart/form-data`
- **Form Field**: `file` (binary stream)

#### `curl` Example
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -F "file=@sample_data/sample.kml"
```

#### Success Response (`201 Created`)
```json
{
  "id": "e9a2b21c-42a1-432d-8ab1-13ef4599a012",
  "filename": "sample.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error": null
}
```

#### Error HTTP Status Codes
- `400 Bad Request`: Empty file uploaded or missing filename.
- `413 Payload Too Large`: Upload file exceeds maximum permitted size of 50 MB.
- `415 Unsupported Media Type`: Extension is not `.zip` or `.kml`.
- `422 Unprocessable Entity`: Corrupt archive, missing `.shp` file, or unreadable KML layers.

---

### 2. `GET /api/files/{id}/`
Retrieve metadata status for a previously processed geospatial file.

#### `curl` Example
```bash
curl -X GET "http://localhost:8000/api/files/e9a2b21c-42a1-432d-8ab1-13ef4599a012/" \
  -H "accept: application/json"
```

#### Success Response (`200 OK`)
```json
{
  "id": "e9a2b21c-42a1-432d-8ab1-13ef4599a012",
  "filename": "sample.kml",
  "feature_count": 3,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error": null
}
```

#### Error HTTP Status Codes
- `404 Not Found`: Unknown file ID.

---

### 3. `GET /api/files/{id}/measurements/`
Retrieve geometry objects, clean property attributes, and calculated metric measurements for every feature.

#### `curl` Example
```bash
curl -X GET "http://localhost:8000/api/files/e9a2b21c-42a1-432d-8ab1-13ef4599a012/measurements/" \
  -H "accept: application/json"
```

#### Success Response (`200 OK`)
```json
{
  "id": "e9a2b21c-42a1-432d-8ab1-13ef4599a012",
  "crs": "EPSG:4326",
  "feature_count": 3,
  "features": [
    {
      "feature_id": 0,
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [[80.200, 13.000], [80.209, 13.000], [80.209, 13.009], [80.200, 13.009], [80.200, 13.000]]
        ]
      },
      "crs": "EPSG:4326",
      "properties": {
        "name": "Chennai Square Polygon (~1 sq km)"
      },
      "measurement": {
        "type": "Polygon",
        "projected_crs": "EPSG:32644",
        "area_sq_m": 966231.84,
        "area_hectares": 96.623,
        "area_sq_km": 0.9662
      },
      "note": null
    },
    {
      "feature_id": 1,
      "geometry_type": "LineString",
      "geometry": {
        "type": "LineString",
        "coordinates": [[80.200, 13.000], [80.200, 13.0087]]
      },
      "crs": "EPSG:4326",
      "properties": {
        "name": "Chennai Test Line (~960m)"
      },
      "measurement": {
        "type": "LineString",
        "projected_crs": "EPSG:32644",
        "length_m": 962.15,
        "length_km": 0.96215
      },
      "note": null
    },
    {
      "feature_id": 2,
      "geometry_type": "Point",
      "geometry": {
        "type": "Point",
        "coordinates": [80.205, 13.005]
      },
      "crs": "EPSG:4326",
      "properties": {
        "name": "Chennai Sample Point"
      },
      "measurement": null,
      "note": "No measurement required for points"
    }
  ]
}
```

#### Error HTTP Status Codes
- `404 Not Found`: Unknown file ID.

---

### 4. `GET /health`
Service health check probe.

#### `curl` Example
```bash
curl -X GET "http://localhost:8000/health"
```

#### Success Response (`200 OK`)
```json
{
  "status": "ok"
}
```

---

## 3. System Architecture & Workflows

### Directory Structure
```
geo-measurement-api/
  app/
    __init__.py
    main.py         # Route handlers, validations, HTTP status mapping
    processing.py   # Safe file reading, zip-slip defense, feature extraction
    crs.py          # EPSG labeling, UTM zone determination, PyProj transformations
    schemas.py      # Pydantic response models
    storage.py      # Thread-safe in-memory storage store
  tests/
    __init__.py
    test_api.py     # Integration and unit test suite
  sample_data/
    sample.kml      # Chennai sample test dataset
  requirements.txt
  README.md
  .gitignore
```

### Application Execution & Data Flow
```
Upload (.zip / .kml) ──► HTTP Validation (Size/Ext) ──► Temp Directory Extraction
                                                                │
                                                Zip-Slip Defense & Format Handler
                                                                │
                                                GeoPandas / pyogrio Layer Reader
                                                                │
                                                Feature Iteration & Property Serialization
                                                                │
                                                EPSG:4326 Centroid UTM Projection
                                                                │
                                                Metric Area / Length Computation
                                                                │
                                                Thread-Safe In-Memory Store ──► HTTP 201 Response
```

---

## 4. Key Design Decisions & Trade-Offs

1. **FastAPI vs. Django / Flask**:
   - *Decision*: Selected FastAPI for high performance (Asynchronous ASGI server), native Pydantic OpenAPI documentation generation, and lightweight request validation.
   - *Alternative Considered*: Django REST Framework (heavy overhead with unneeded ORM for simple in-memory requirements) or Flask (lacks built-in request validation and async I/O).

2. **Per-Feature UTM Projection vs. Single Global Projection vs. Geodesic (`pyproj.Geod`)**:
   - *Decision*: Transform each feature to WGS84 (`EPSG:4326`), calculate its local centroid, and project to the optimal local UTM Zone (`EPSG:326xx` / `EPSG:327xx`).
   - *Alternatives Considered*:
     - *Single fixed projected CRS*: Causes severe spatial distortion for geometries spread across longitudes.
     - *Geodesic measurement (`pyproj.Geod.geometry_area_perimeter`)*: Highly accurate for global geometries, but does not yield a standard projected geometry in linear metric space. Per-feature UTM balances standard spatial projection with minimal local distortion.

3. **Synchronous Request Processing vs. Asynchronous Task Queues**:
   - *Decision*: Process files synchronously in worker threads for files $\le 50\text{ MB}$.
   - *Alternative Considered*: Background task queues (Celery/Redis). Synchronous execution simplifies deployment while staying well under HTTP timeout thresholds for standard files.

4. **Thread-Safe In-Memory Store vs. Relational Database**:
   - *Decision*: Encapsulated Python dictionary with `threading.Lock()`.
   - *Alternative Considered*: SQLite / PostgreSQL. In-memory storage satisfies strict zero-dependency deployment while ensuring thread-safety under concurrent Uvicorn workers.

5. **Graceful Fault Tolerance for Invalid Geometries**:
   - *Decision*: Wrap each individual feature's measurement calculation in isolated `try/except` blocks.
   - *Rationale*: Malformed geometries or missing attributes in one row will populate a descriptive `note` field without failing the upload request for the remaining valid features.

---

## 5. Key Learnings & Future Scope

### Technical Learnings
- **Geographic vs. Projected Coordinate Systems**: Geodetic coordinates (latitude/longitude in degrees) cannot be directly used for planar area or length calculation because degree distances vary by latitude.
- **Dynamic UTM Zone Selection**: UTM zone calculation formula:
  $$\text{Zone} = \lfloor(\text{lon} + 180) / 6\rfloor + 1$$
  where northern hemisphere maps to `EPSG:326xx` and southern to `EPSG:327xx`.
- **KML Multi-Layer Handling**: KML files often encapsulate multiple document layers. Utilizing `pyogrio.list_layers` ensures all layers are concatenated without missing geometries.
- **Zip-Slip Vulnerability Protection**: Validating archive file paths against directory traversal (`..`, absolute paths, leading slashes) prevents arbitrary file overwrites.

### Future Scope & Roadmap
1. **Persistent Spatial Storage**: Transition from in-memory dictionary storage to PostgreSQL with PostGIS extension or S3 object storage for raw uploaded files.
2. **Asynchronous Background Processing**: Introduce Celery or RQ workers with status polling (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`) for large datasets (>50 MB).
3. **Geodesic Measurement Support**: Implement `pyproj.Geod` calculations for large geographic features spanning multiple UTM zones.
4. **Pagination & Spatial Filtering**: Support `limit`/`offset` pagination and bounding-box (`bbox`) spatial filtering on `/measurements/`.
5. **Additional Geospatial Formats**: Expand driver support to include GeoJSON (`.geojson`), GeoPackage (`.gpkg`), and FlatGeobuf (`.fgb`).
6. **Authentication & Authorization**: Integrate JWT or OAuth2 bearer tokens for secure user-level access.
7. **Containerization & CI/CD**: Provide `Dockerfile`, `docker-compose.yml`, and GitHub Actions workflow pipelines for automated testing and deployment.
