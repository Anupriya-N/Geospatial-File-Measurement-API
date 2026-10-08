"""CRS selection, transformation, and labeling helper utilities."""

from typing import Any, Tuple
from pyproj import CRS, Transformer
from shapely.ops import transform as shapely_ops_transform
from shapely.geometry.base import BaseGeometry


def crs_label(crs_input: Any) -> str:
    """Return 'EPSG:xxxx' if available, otherwise fall back to string representation.

    Args:
        crs_input: CRS object, EPSG code string, or None.

    Returns:
        String label such as 'EPSG:4326' or 'EPSG:32644'.
    """
    if crs_input is None:
        return "EPSG:4326"

    try:
        if isinstance(crs_input, CRS):
            crs_obj = crs_input
        else:
            crs_obj = CRS.from_user_input(crs_input)

        epsg_code = crs_obj.to_epsg()
        if epsg_code is not None:
            return f"EPSG:{epsg_code}"
        return crs_obj.to_string()
    except Exception:
        return str(crs_input) if crs_input else "EPSG:4326"


def determine_utm_crs(lon: float, lat: float) -> str:
    """Determine the appropriate UTM projected CRS code based on longitude and latitude.

    Args:
        lon: Longitude in decimal degrees [-180, 180].
        lat: Latitude in decimal degrees [-90, 90].

    Returns:
        EPSG string, e.g., 'EPSG:32644' for northern hemisphere or 'EPSG:32744' for southern.
    """
    # Bound longitude between -180 and 180
    lon = max(-180.0, min(180.0, lon))
    zone = int((lon + 180) // 6) + 1
    zone = max(1, min(60, zone))

    if lat >= 0:
        epsg_code = 32600 + zone
    else:
        epsg_code = 32700 + zone

    return f"EPSG:{epsg_code}"


def transform_geometry(
    geom: BaseGeometry,
    source_crs_input: Any,
    target_crs_input: Any,
) -> BaseGeometry:
    """Transform a Shapely geometry from source CRS to target CRS.

    Args:
        geom: Shapely geometry instance.
        source_crs_input: Source CRS representation.
        target_crs_input: Target CRS representation.

    Returns:
        Transformed Shapely geometry instance.
    """
    if geom is None or geom.is_empty:
        return geom

    source_crs = (
        source_crs_input
        if isinstance(source_crs_input, CRS)
        else CRS.from_user_input(source_crs_input)
    )
    target_crs = (
        target_crs_input
        if isinstance(target_crs_input, CRS)
        else CRS.from_user_input(target_crs_input)
    )

    if source_crs == target_crs:
        return geom

    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    return shapely_ops_transform(transformer.transform, geom)




def project_geometry_to_utm(
    geom: BaseGeometry,
    source_crs_input: Any,
) -> Tuple[BaseGeometry, str]:
    """Transform geometry to EPSG:4326, pick appropriate UTM zone, and project into UTM CRS.

    Args:
        geom: Input Shapely geometry.
        source_crs_input: Source CRS representation of the input geometry.

    Returns:
        Tuple of (projected_geometry, projected_utm_crs_string).
    """
    # 1. Transform to EPSG:4326
    geom_4326 = transform_geometry(geom, source_crs_input, "EPSG:4326")

    # 2. Pick UTM zone from centroid
    centroid = geom_4326.centroid
    utm_crs_str = determine_utm_crs(centroid.x, centroid.y)

    # 3. Project into UTM CRS
    projected_geom = transform_geometry(geom_4326, "EPSG:4326", utm_crs_str)

    return projected_geom, utm_crs_str
