"""FastAPI main application routes, error handlers, and validation."""

import uuid
from typing import Any, Dict

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.processing import FileProcessingError, process_geospatial_file
from app.schemas import FileMeasurementsResponse, FileResponse, HealthResponse
from app.storage import store

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB Limit

app = FastAPI(
    title="Geospatial File Measurement API",
    description="Backend service for geospatial file extraction, CRS projection, and feature measurement.",
    version="1.0.0",
)


@app.exception_handler(FileProcessingError)
async def file_processing_error_handler(request: Any, exc: FileProcessingError):
    """Map FileProcessingError exceptions to HTTP 422 Unprocessable Entity."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint returning service operational status."""
    return {"status": "ok"}


@app.post(
    "/api/files/",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Files"],
)
async def upload_file(file: UploadFile = File(...)):
    """Upload and process a geospatial file (.zip Shapefile or .kml).

    Validates file extension, size, and integrity. Extracts features and computes measurements.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing",
        )

    filename = file.filename
    ext = filename.split(".")[-1].lower() if "." in filename else ""

    if ext not in ("zip", "kml"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type extension '.{ext}'. Only .zip and .kml are supported.",
        )

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of 50 MB",
        )

    # Process file and extract measurements
    try:
        crs_label_str, feature_count, features = process_geospatial_file(
            content, filename
        )
    except FileProcessingError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Corrupt or unreadable file: {str(e)}",
        ) from e

    file_id = str(uuid.uuid4())
    record = {
        "id": file_id,
        "filename": filename,
        "feature_count": feature_count,
        "crs": crs_label_str,
        "status": "COMPLETED",
        "error": None,
        "features": features,
    }

    store.save(file_id, record)

    return FileResponse(
        id=record["id"],
        filename=record["filename"],
        feature_count=record["feature_count"],
        crs=record["crs"],
        status=record["status"],
        error=record["error"],
    )


@app.get("/api/files/{file_id}/", response_model=FileResponse, tags=["Files"])
async def get_file_info(file_id: str):
    """Retrieve metadata information for a previously processed file."""
    record = store.get(file_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File record with id '{file_id}' not found",
        )

    return FileResponse(
        id=record["id"],
        filename=record["filename"],
        feature_count=record["feature_count"],
        crs=record["crs"],
        status=record["status"],
        error=record["error"],
    )


@app.get(
    "/api/files/{file_id}/measurements/",
    response_model=FileMeasurementsResponse,
    tags=["Files"],
)
async def get_file_measurements(file_id: str):
    """Retrieve features and calculated measurements for a processed file."""
    record = store.get(file_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File record with id '{file_id}' not found",
        )

    return FileMeasurementsResponse(
        id=record["id"],
        crs=record["crs"],
        feature_count=record["feature_count"],
        features=record["features"],
    )
