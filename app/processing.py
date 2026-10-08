"""Geospatial file reading, feature extraction, property cleaning, and measurement calculations."""

import math
import os
import tempfile
import zipfile
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry

from app.crs import crs_label, project_geometry_to_utm


class FileProcessingError(Exception):
    """Custom exception raised when file processing, reading, or extraction fails."""

    pass


def clean_value(val: Any) -> Any:
    """Convert numpy, pandas, date, or NaN values to JSON-safe native Python types."""
    if val is None:
        return None

    # Handle pandas / numpy NA and NaN
    if pd.isna(val):
        return None

    # Handle floats including NaN and infinity
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)

    # Handle numpy integers and booleans
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)

    # Handle date / datetime objects
    if isinstance(val, (datetime, date, pd.Timestamp)):
        return val.isoformat()

    # Handle lists or arrays recursively
    if isinstance(val, (list, tuple, np.ndarray)):
        return [clean_value(item) for item in val]

    # Handle dicts recursively
    if isinstance(val, dict):
        return {str(k): clean_value(v) for k, v in val.items()}

    return str(val) if not isinstance(val, (str, int, float, bool)) else val


def clean_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    """Clean a dictionary of feature properties for JSON serialization."""
    cleaned = {}
    for key, value in properties.items():
        if key.lower() == "geometry":
            continue
        cleaned[str(key)] = clean_value(value)
    return cleaned


def _safe_extract_zip(zip_bytes: bytes, extract_dir: str) -> str:
    """Extract a zip archive safely, protecting against zip-slip vulnerabilities.

    Returns the absolute path to the first .shp file found.
    """
    zip_path = os.path.join(extract_dir, "upload.zip")
    with open(zip_path, "wb") as f:
        f.write(zip_bytes)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.infolist():
                member_path = member.filename
                # Zip-slip protection checks
                if (
                    member_path.startswith("/")
                    or member_path.startswith("\\")
                    or ".." in member_path
                    or (len(member_path) > 1 and member_path[1] == ":")
                ):
                    raise FileProcessingError(
                        "Zip archive contains unsafe relative paths or zip-slip attempt"
                    )

                # Ensure extracted path resides strictly inside extract_dir
                target_path = os.path.abspath(os.path.join(extract_dir, member_path))
                if not target_path.startswith(os.path.abspath(extract_dir)):
                    raise FileProcessingError(
                        "Zip archive contains path directory traversal attempt"
                    )

            zf.extractall(extract_dir)
    except zipfile.BadZipFile as e:
        raise FileProcessingError(f"Corrupt or invalid zip archive: {str(e)}") from e
    except FileProcessingError:
        raise
    except Exception as e:
        raise FileProcessingError(f"Failed to extract zip archive: {str(e)}") from e

    # Find first .shp file in extracted tree
    shp_path: Optional[str] = None
    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.lower().endswith(".shp"):
                shp_path = os.path.join(root, file)
                break
        if shp_path:
            break

    if not shp_path:
        raise FileProcessingError("No .shp file found in zip archive")

    return shp_path


def _read_kml(kml_bytes: bytes, extract_dir: str) -> gpd.GeoDataFrame:
    """Read all layers from a KML file into a single concatenated GeoDataFrame."""
    kml_path = os.path.join(extract_dir, "upload.kml")
    with open(kml_path, "wb") as f:
        f.write(kml_bytes)

    try:
        layers_info = pyogrio.list_layers(kml_path)
    except Exception as e:
        raise FileProcessingError(f"Corrupt or unreadable KML file: {str(e)}") from e

    layer_names: List[str] = []
    if len(layers_info) > 0:
        for item in layers_info:
            if isinstance(item, (list, tuple, np.ndarray)) and len(item) > 0:
                layer_names.append(str(item[0]))
            elif isinstance(item, str):
                layer_names.append(item)

    gdfs: List[gpd.GeoDataFrame] = []
    if layer_names:
        for lname in layer_names:
            try:
                gdf_layer = gpd.read_file(kml_path, layer=lname, engine="pyogrio")
                if not gdf_layer.empty:
                    gdfs.append(gdf_layer)
            except Exception:
                # Continue if an individual layer read fails or is empty
                continue

    if not gdfs:
        # Fallback to standard read_file if list_layers returned nothing or reading layers failed
        try:
            gdf = gpd.read_file(kml_path, engine="pyogrio")
            gdfs.append(gdf)
        except Exception as e:
            raise FileProcessingError(
                f"Failed to read KML file: {str(e)}"
            ) from e

    if not gdfs:
        raise FileProcessingError("KML file contains no readable layers or features")

    combined_gdf = pd.concat(gdfs, ignore_index=True)
    if combined_gdf.crs is None:
        combined_gdf.set_crs("EPSG:4326", inplace=True)

    return combined_gdf


def compute_feature_measurement(
    geom: Optional[BaseGeometry],
    source_crs: Any,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Compute measurement dictionary and note for a single feature geometry.

    Returns:
        Tuple of (measurement_dict, note_string).
    """
    if source_crs is None:
        return None, "Source CRS missing; cannot measure"

    if geom is None or geom.is_empty:
        return None, "Empty or missing geometry"

    geom_type = geom.geom_type

    if geom_type in ("Polygon", "MultiPolygon"):
        projected_geom, utm_crs_str = project_geometry_to_utm(geom, source_crs)
        area_sq_m = float(projected_geom.area)
        area_hectares = area_sq_m / 10000.0
        area_sq_km = area_sq_m / 1000000.0
        measurement = {
            "type": geom_type,
            "projected_crs": utm_crs_str,
            "area_sq_m": area_sq_m,
            "area_hectares": area_hectares,
            "area_sq_km": area_sq_km,
        }
        return measurement, None

    if geom_type in ("LineString", "MultiLineString"):
        projected_geom, utm_crs_str = project_geometry_to_utm(geom, source_crs)
        length_m = float(projected_geom.length)
        length_km = length_m / 1000.0
        measurement = {
            "type": geom_type,
            "projected_crs": utm_crs_str,
            "length_m": length_m,
            "length_km": length_km,
        }
        return measurement, None

    if geom_type in ("Point", "MultiPoint"):
        return None, "No measurement required for points"

    return None, f"Measurement not supported for geometry type {geom_type}"


def process_geospatial_file(
    file_bytes: bytes, filename: str
) -> Tuple[str, int, List[Dict[str, Any]]]:
    """Process uploaded geospatial file (.zip or .kml) and extract features with measurements.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        filename: Original filename.

    Returns:
        Tuple of (crs_string, feature_count, features_list).

    Raises:
        FileProcessingError: If the file is unreadable, invalid, corrupt, or unsupported.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".zip", ".kml"):
        raise FileProcessingError(f"Unsupported file type '{ext}'")

    with tempfile.TemporaryDirectory() as tmp_dir:
        if ext == ".zip":
            shp_path = _safe_extract_zip(file_bytes, tmp_dir)
            try:
                gdf = gpd.read_file(shp_path, engine="pyogrio")
            except Exception as e:
                raise FileProcessingError(
                    f"Failed to read Shapefile: {str(e)}"
                ) from e
        else:  # .kml
            gdf = _read_kml(file_bytes, tmp_dir)

        if gdf.empty:
            raise FileProcessingError("Geospatial file contains 0 features")

        source_crs = gdf.crs
        source_crs_label_str = crs_label(source_crs)

        features: List[Dict[str, Any]] = []

        for idx, row in gdf.iterrows():
            geom = row.geometry if hasattr(row, "geometry") else None
            geom_type = geom.geom_type if geom is not None and not geom.is_empty else None
            geom_dict = mapping(geom) if geom is not None and not geom.is_empty else None

            # Convert row properties
            prop_dict = row.drop("geometry").to_dict() if hasattr(row, "geometry") else row.to_dict()
            cleaned_props = clean_properties(prop_dict)

            # Per-feature measurement calculation wrapped safely
            measurement: Optional[Dict[str, Any]] = None
            note: Optional[str] = None

            try:
                measurement, note = compute_feature_measurement(geom, source_crs)
            except Exception as e:
                measurement = None
                note = f"Error computing measurement: {str(e)}"

            feature_item = {
                "feature_id": int(idx),
                "geometry_type": geom_type,
                "geometry": geom_dict,
                "crs": source_crs_label_str if source_crs is not None else None,
                "properties": cleaned_props,
                "measurement": measurement,
                "note": note,
            }
            features.append(feature_item)

        return source_crs_label_str, len(features), features
