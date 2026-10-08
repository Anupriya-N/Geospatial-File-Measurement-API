"""Pydantic schemas for the Geospatial File Measurement API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class FileResponse(BaseModel):
    """Response model for uploaded file info and metadata status."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique identifier for the uploaded file")
    filename: str = Field(..., description="Original filename of the uploaded file")
    feature_count: int = Field(..., description="Total number of features in the geospatial file")
    crs: str = Field(..., description="Source CRS or EPSG representation")
    status: str = Field("COMPLETED", description="Processing status of the file")
    error: Optional[str] = Field(None, description="Error details if processing failed")


class FeatureItem(BaseModel):
    """Response model for individual feature geometry, properties, and measurement."""

    model_config = ConfigDict(extra="ignore")

    feature_id: int = Field(..., description="0-indexed feature integer identifier")
    geometry_type: Optional[str] = Field(None, description="Shapely geometry type string")
    geometry: Optional[Dict[str, Any]] = Field(None, description="GeoJSON geometry dictionary")
    crs: Optional[str] = Field(None, description="Feature CRS or file source CRS")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature property attributes")
    measurement: Optional[Dict[str, Any]] = Field(None, description="Calculated area or length measurement object")
    note: Optional[str] = Field(None, description="Additional note or reason if measurement is absent")


class FileMeasurementsResponse(BaseModel):
    """Response model for file feature measurements details."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique identifier for the uploaded file")
    crs: str = Field(..., description="Source CRS representation")
    feature_count: int = Field(..., description="Total number of features")
    features: List[FeatureItem] = Field(..., description="List of feature measurement details")


class HealthResponse(BaseModel):
    """Health check endpoint response model."""

    model_config = ConfigDict(extra="ignore")

    status: str = Field("ok", description="Health status string")
