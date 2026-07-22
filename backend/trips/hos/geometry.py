"""Polyline helpers: cumulative distance/time + binary search interpolation."""

from __future__ import annotations

from typing import List, Sequence, Tuple


Point = Tuple[float, float]  # (lat, lng)


def haversine_miles(a: Point, b: Point) -> float:
    from math import atan2, cos, radians, sin, sqrt

    lat1, lon1 = map(radians, a)
    lat2, lon2 = map(radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 3958.7613 * 2 * atan2(sqrt(h), sqrt(1 - h))


def build_cumulative(coords: Sequence[Point], total_drive_hours: float):
    """
    Return (cum_miles[], cum_hours[], coords).
    Time is distributed proportional to distance along the polyline.
    """
    if not coords:
        return [], [], []

    miles = [0.0]
    for i in range(1, len(coords)):
        miles.append(miles[-1] + haversine_miles(coords[i - 1], coords[i]))

    total_miles = miles[-1] or 1.0
    hours = [m / total_miles * total_drive_hours for m in miles]
    return miles, hours, list(coords)


def _interp(cum: List[float], coords: List[Point], target: float) -> Point:
    if not coords:
        return (0.0, 0.0)
    if target <= cum[0]:
        return coords[0]
    if target >= cum[-1]:
        return coords[-1]

    lo, hi = 0, len(cum) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if cum[mid] <= target:
            lo = mid
        else:
            hi = mid

    span = cum[hi] - cum[lo] or 1e-9
    t = (target - cum[lo]) / span
    lat = coords[lo][0] + (coords[hi][0] - coords[lo][0]) * t
    lng = coords[lo][1] + (coords[hi][1] - coords[lo][1]) * t
    return (lat, lng)


def point_at_miles(cum_miles: List[float], coords: List[Point], miles: float) -> Point:
    return _interp(cum_miles, coords, miles)


def point_at_hours(cum_hours: List[float], coords: List[Point], hours: float) -> Point:
    return _interp(cum_hours, coords, hours)


def downsample_geometry(
    coords: Sequence[Sequence[float]], max_points: int = 500
) -> List[List[float]]:
    """Keep map payloads light for Leaflet without losing overall shape."""
    n = len(coords)
    if n <= max_points or max_points < 3:
        return [list(c) for c in coords]
    out = [list(coords[0])]
    step = (n - 1) / (max_points - 1)
    for i in range(1, max_points - 1):
        idx = int(round(i * step))
        out.append(list(coords[idx]))
    out.append(list(coords[-1]))
    return out
