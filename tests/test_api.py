"""Integration and unit test suite for the Geospatial File Measurement API."""

import io
import os
import zipfile
import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from app.main import app
from app.storage import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_storage():
    """Clear the thread-safe storage before each test run."""
    store.clear()
    yield
    store.clear()


def test_health_check():
    """Test /health endpoint returns HTTP 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_kml_flow():
    """Test full upload and measurement flow for sample.kml file."""
    kml_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "sample_data", "sample.kml"
    )
    assert os.path.exists(kml_path), "sample.kml file must exist"

    with open(kml_path, "rb") as f:
        response = client.post(
            "/api/files/",
            files={"file": ("sample.kml", f, "application/vnd.google-earth.kml+xml")},
        )

    assert response.status_code == 201
    data = response.json()
    file_id = data["id"]
    assert data["filename"] == "sample.kml"
    assert data["feature_count"] == 3
    assert data["crs"] == "EPSG:4326"
    assert data["status"] == "COMPLETED"
    assert data["error"] is None

    # Test GET /api/files/{id}/
    info_resp = client.get(f"/api/files/{file_id}/")
    assert info_resp.status_code == 200
    assert info_resp.json()["id"] == file_id

    # Test GET /api/files/{id}/measurements/
    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["id"] == file_id
    assert meas_data["feature_count"] == 3
    features = meas_data["features"]
    assert len(features) == 3

    # Polygon feature check
    poly_feat = features[0]
    assert poly_feat["geometry_type"] in ("Polygon", "MultiPolygon")
    poly_meas = poly_feat["measurement"]
    assert poly_meas is not None
    assert poly_meas["type"] == "Polygon"
    assert poly_meas["projected_crs"] == "EPSG:32644"
    assert 0.9e6 <= poly_meas["area_sq_m"] <= 1.1e6
    assert poly_meas["area_hectares"] > 0
    assert poly_meas["area_sq_km"] > 0
    assert poly_feat["note"] is None

    # LineString feature check
    line_feat = features[1]
    assert line_feat["geometry_type"] in ("LineString", "MultiLineString")
    line_meas = line_feat["measurement"]
    assert line_meas is not None
    assert line_meas["type"] == "LineString"
    assert 950.0 <= line_meas["length_m"] <= 1000.0
    assert line_feat["note"] is None

    # Point feature check
    point_feat = features[2]
    assert point_feat["geometry_type"] in ("Point", "MultiPoint")
    assert point_feat["measurement"] is None
    assert point_feat["note"] == "No measurement required for points"


def test_shapefile_zip_flow(tmp_path):
    """Test creating a Shapefile polygon, zipping it, uploading, and checking measurements."""
    shp_dir = tmp_path / "shp_source"
    shp_dir.mkdir()
    shp_file = shp_dir / "test_polygon.shp"

    # Polygon in WGS84 around Chennai
    poly = Polygon(
        [(80.200, 13.000), (80.209, 13.000), (80.209, 13.009), (80.200, 13.009)]
    )
    gdf = gpd.GeoDataFrame(
        [{"name": "Test Polygon", "category": "Zone A"}],
        geometry=[poly],
        crs="EPSG:4326",
    )
    gdf.to_file(shp_file, engine="pyogrio")

    # Zip all shapefile sidecar files
    zip_bytes_io = io.BytesIO()
    with zipfile.ZipFile(zip_bytes_io, "w") as zf:
        for root, _, files in os.walk(shp_dir):
            for file in files:
                full_path = os.path.join(root, file)
                zf.write(full_path, arcname=file)

    zip_bytes = zip_bytes_io.getvalue()

    # Upload zip
    response = client.post(
        "/api/files/",
        files={"file": ("shapefile.zip", zip_bytes, "application/zip")},
    )

    assert response.status_code == 201
    data = response.json()
    file_id = data["id"]
    assert data["feature_count"] == 1
    assert data["status"] == "COMPLETED"

    meas_resp = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    feature = meas_data["features"][0]
    assert feature["properties"]["name"] == "Test Polygon"
    assert feature["properties"]["category"] == "Zone A"
    assert feature["measurement"]["projected_crs"] == "EPSG:32644"
    assert 0.9e6 <= feature["measurement"]["area_sq_m"] <= 1.1e6


def test_unsupported_file_extension():
    """Test uploading a file with an unsupported extension returns 415."""
    response = client.post(
        "/api/files/",
        files={"file": ("test.txt", b"some text content", "text/plain")},
    )
    assert response.status_code == 415
    assert "Unsupported file type extension" in response.json()["detail"]


def test_empty_file_upload():
    """Test uploading an empty file returns 400."""
    response = client.post(
        "/api/files/",
        files={"file": ("test.kml", b"", "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_corrupt_zip_file_upload():
    """Test uploading a corrupt zip file returns 422."""
    response = client.post(
        "/api/files/",
        files={"file": ("fake.zip", b"not a real zip content", "application/zip")},
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_corrupt_kml_file_upload():
    """Test uploading a garbage KML file returns 422."""
    response = client.post(
        "/api/files/",
        files={
            "file": (
                "garbage.kml",
                b"<kml>corrupt content without geometries</kml>",
                "application/vnd.google-earth.kml+xml",
            )
        },
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_nonexistent_file_id_returns_404():
    """Test querying nonexistent file IDs returns HTTP 404."""
    unknown_id = "00000000-0000-0000-0000-000000000000"
    resp1 = client.get(f"/api/files/{unknown_id}/")
    assert resp1.status_code == 404

    resp2 = client.get(f"/api/files/{unknown_id}/measurements/")
    assert resp2.status_code == 404
