"""Geocoding + routing via OpenRouteService, with OSRM/Nominatim fallback."""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

Point = Tuple[float, float]

_geocode_cache: Dict[str, Point] = {}
_reverse_cache: Dict[str, str] = {}

ORS_BASE = "https://api.openrouteservice.org"
OSRM_BASE = "https://router.project-osrm.org"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
USER_AGENT = "ELDTripPlanner/1.0 (assessment; contact: github.com/Ateeb-333)"


class RoutingError(Exception):
    pass


def _ors_key() -> Optional[str]:
    return os.environ.get("ORS_API_KEY") or os.environ.get("OPENROUTESERVICE_API_KEY")


def geocode(query: str) -> Point:
    key = query.strip().lower()
    if key in _geocode_cache:
        return _geocode_cache[key]

    ors = _ors_key()
    if ors:
        try:
            point = _ors_geocode(query, ors)
            _geocode_cache[key] = point
            return point
        except Exception as exc:
            logger.warning("ORS geocode failed (%s); falling back to Nominatim", exc)

    point = _nominatim_geocode(query)
    _geocode_cache[key] = point
    return point


def reverse_geocode(lat: float, lng: float) -> str:
    cache_key = f"{lat:.4f},{lng:.4f}"
    if cache_key in _reverse_cache:
        return _reverse_cache[cache_key]

    ors = _ors_key()
    label = None
    if ors:
        try:
            label = _ors_reverse(lat, lng, ors)
        except Exception as exc:
            logger.warning("ORS reverse failed (%s)", exc)

    if not label:
        try:
            label = _nominatim_reverse(lat, lng)
        except Exception:
            label = f"{lat:.3f}, {lng:.3f}"

    _reverse_cache[cache_key] = label
    return label


def route(points: List[Point]) -> dict:
    """
    Route through waypoints. Returns:
      geometry: [[lat, lng], ...]
      total_distance_miles
      total_drive_hours
      legs: [{distance_miles, duration_hours}, ...]
    """
    if len(points) < 2:
        raise RoutingError("Need at least two points to route")

    ors = _ors_key()
    if ors:
        try:
            return _ors_route(points, ors, profile="driving-hgv")
        except Exception as exc:
            logger.warning("ORS driving-hgv failed (%s); trying driving-car", exc)
            try:
                return _ors_route(points, ors, profile="driving-car")
            except Exception as exc2:
                logger.warning("ORS driving-car failed (%s); falling back to OSRM", exc2)

    return _osrm_route(points)


def _ors_geocode(query: str, api_key: str) -> Point:
    resp = requests.get(
        f"{ORS_BASE}/geocode/search",
        params={"api_key": api_key, "text": query, "size": 1},
        timeout=30,
    )
    resp.raise_for_status()
    features = resp.json().get("features") or []
    if not features:
        raise RoutingError(f"Could not find that location: {query}")
    lng, lat = features[0]["geometry"]["coordinates"]
    return (lat, lng)


def _ors_reverse(lat: float, lng: float, api_key: str) -> str:
    resp = requests.get(
        f"{ORS_BASE}/geocode/reverse",
        params={"api_key": api_key, "point.lat": lat, "point.lon": lng, "size": 1},
        timeout=30,
    )
    resp.raise_for_status()
    features = resp.json().get("features") or []
    if not features:
        return f"{lat:.3f}, {lng:.3f}"
    props = features[0].get("properties") or {}
    city = props.get("locality") or props.get("county") or props.get("name") or ""
    state = props.get("region_a") or props.get("region") or ""
    if city and state:
        return f"{city}, {state}"
    return props.get("label") or f"{lat:.3f}, {lng:.3f}"


def _ors_route(points: List[Point], api_key: str, profile: str) -> dict:
    coords = [[lng, lat] for lat, lng in points]
    resp = requests.post(
        f"{ORS_BASE}/v2/directions/{profile}/geojson",
        json={"coordinates": coords, "units": "m"},
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        timeout=60,
    )
    if resp.status_code >= 400:
        raise RoutingError(resp.text[:300])
    data = resp.json()
    features = data.get("features") or []
    if not features:
        raise RoutingError("No route found")
    feat = features[0]
    geometry_coords = feat["geometry"]["coordinates"]
    # GeoJSON is [lng, lat]
    geometry = [[c[1], c[0]] for c in geometry_coords]
    summary = feat["properties"].get("summary") or {}
    # ORS may put summary under segments
    if not summary and feat["properties"].get("segments"):
        segs = feat["properties"]["segments"]
        distance_m = sum(s.get("distance", 0) for s in segs)
        duration_s = sum(s.get("duration", 0) for s in segs)
    else:
        distance_m = summary.get("distance", 0)
        duration_s = summary.get("duration", 0)

    segments = feat["properties"].get("segments") or []
    legs = []
    if segments:
        for s in segments:
            legs.append(
                {
                    "distance_miles": round(s.get("distance", 0) / 1609.344, 2),
                    "duration_hours": round(s.get("duration", 0) / 3600.0, 4),
                }
            )
    else:
        # Split evenly across legs if only summary available
        n = len(points) - 1
        for _ in range(n):
            legs.append(
                {
                    "distance_miles": round((distance_m / 1609.344) / n, 2),
                    "duration_hours": round((duration_s / 3600.0) / n, 4),
                }
            )

    return {
        "geometry": geometry,
        "total_distance_miles": round(distance_m / 1609.344, 2),
        "total_drive_hours": round(duration_s / 3600.0, 4),
        "legs": legs,
    }


def _nominatim_geocode(query: str) -> Point:
    time.sleep(1.05)  # be polite to public Nominatim
    resp = requests.get(
        f"{NOMINATIM_BASE}/search",
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise RoutingError(f"Could not find that location: {query}")
    return (float(data[0]["lat"]), float(data[0]["lon"]))


def _nominatim_reverse(lat: float, lng: float) -> str:
    time.sleep(1.05)
    resp = requests.get(
        f"{NOMINATIM_BASE}/reverse",
        params={"lat": lat, "lon": lng, "format": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    addr = data.get("address") or {}
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or ""
    state = addr.get("state_code") or addr.get("state") or ""
    if city and state:
        # Prefer short state codes when present
        if len(state) > 2:
            return f"{city}, {state}"
        return f"{city}, {state}"
    return data.get("display_name", f"{lat:.3f}, {lng:.3f}").split(",")[0]


def _osrm_route(points: List[Point]) -> dict:
    coord_str = ";".join(f"{lng},{lat}" for lat, lng in points)
    url = f"{OSRM_BASE}/route/v1/driving/{coord_str}"
    resp = requests.get(
        url,
        params={"overview": "full", "geometries": "geojson", "steps": "false"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError("No route found between those locations")
    r = data["routes"][0]
    geometry = [[c[1], c[0]] for c in r["geometry"]["coordinates"]]
    legs = []
    for leg in r.get("legs") or []:
        legs.append(
            {
                "distance_miles": round(leg.get("distance", 0) / 1609.344, 2),
                "duration_hours": round(leg.get("duration", 0) / 3600.0, 4),
            }
        )
    return {
        "geometry": geometry,
        "total_distance_miles": round(r.get("distance", 0) / 1609.344, 2),
        "total_drive_hours": round(r.get("duration", 0) / 3600.0, 4),
        "legs": legs,
    }
