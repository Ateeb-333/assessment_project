"""
Pure FMCSA Hours-of-Service planner. No Django imports.

Clocks (property-carrying, 70/8):
  - 11h driving per shift
  - 14h on-duty window (elapsed wall time; does not pause)
  - 8h driving since last ≥30 min non-driving break
  - 70h on-duty in 8 days (scalar; recovered only via 34h restart)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Tuple


# Work in integer minutes to avoid float drift on log totals.
DRIVE_LIMIT_MIN = 11 * 60
WINDOW_LIMIT_MIN = 14 * 60
BREAK_DRIVE_LIMIT_MIN = 8 * 60
BREAK_DURATION_MIN = 30
REST_DURATION_MIN = 10 * 60
RESTART_DURATION_MIN = 34 * 60
FUEL_DURATION_MIN = 30
CYCLE_LIMIT_MIN = 70 * 60
FUEL_INTERVAL_MILES = 1000.0


class Status(str, Enum):
    OFF = "OFF"
    SB = "SB"
    D = "D"
    ON = "ON"


@dataclass
class WorkItem:
    kind: str  # "drive" | "on_duty"
    duration_hours: float = 0.0
    distance_miles: float = 0.0
    note: str = ""
    location: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None


@dataclass
class Segment:
    start: datetime
    end: datetime
    status: str
    location: str = ""
    note: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "start": self.start.isoformat(timespec="seconds"),
            "end": self.end.isoformat(timespec="seconds"),
            "status": self.status,
            "location": self.location,
            "note": self.note,
            "lat": self.lat,
            "lng": self.lng,
        }


@dataclass
class Stop:
    type: str  # pickup | dropoff | fuel | break | rest | restart
    lat: Optional[float]
    lng: Optional[float]
    label: str
    arrival: datetime
    duration_hours: float
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "lat": self.lat,
            "lng": self.lng,
            "label": self.label,
            "arrival": self.arrival.isoformat(timespec="seconds"),
            "duration_hours": round(self.duration_hours, 4),
            "note": self.note,
        }


@dataclass
class ClockState:
    now: datetime
    driving_this_shift: int = 0  # minutes
    window_start: Optional[datetime] = None
    driving_since_break: int = 0  # minutes
    cycle_used: int = 0  # minutes
    miles_since_fuel: float = 0.0


@dataclass
class PlanResult:
    segments: List[Segment] = field(default_factory=list)
    stops: List[Stop] = field(default_factory=list)
    cycle_used_start: float = 0.0
    cycle_used_end: float = 0.0
    restarts_taken: int = 0


def _hours(minutes: int) -> float:
    return round(minutes / 60.0, 4)


def _window_remaining(state: ClockState) -> int:
    if state.window_start is None:
        return WINDOW_LIMIT_MIN
    elapsed = int((state.now - state.window_start).total_seconds() // 60)
    return max(0, WINDOW_LIMIT_MIN - elapsed)


def _ensure_window(state: ClockState) -> None:
    if state.window_start is None:
        state.window_start = state.now


def _emit(
    segments: List[Segment],
    state: ClockState,
    status: str,
    minutes: int,
    location: str = "",
    note: str = "",
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> Segment:
    if minutes <= 0:
        raise ValueError("segment duration must be positive")
    start = state.now
    end = start + timedelta(minutes=minutes)
    seg = Segment(
        start=start,
        end=end,
        status=status,
        location=location,
        note=note,
        lat=lat,
        lng=lng,
    )
    segments.append(seg)
    state.now = end
    return seg


def _add_on_duty(state: ClockState, minutes: int) -> None:
    _ensure_window(state)
    state.cycle_used += minutes


def _add_driving(state: ClockState, minutes: int, miles: float) -> None:
    _ensure_window(state)
    state.driving_this_shift += minutes
    state.driving_since_break += minutes
    state.cycle_used += minutes
    state.miles_since_fuel += miles


def _reset_after_rest(state: ClockState) -> None:
    state.driving_this_shift = 0
    state.driving_since_break = 0
    state.window_start = None


def _maybe_restart(state: ClockState, segments: List[Segment], stops: List[Stop], location: str) -> int:
    """Insert 34h OFF restart if cycle is exhausted. Returns restarts added."""
    restarts = 0
    while state.cycle_used >= CYCLE_LIMIT_MIN:
        _emit(
            segments,
            state,
            Status.OFF,
            RESTART_DURATION_MIN,
            location=location,
            note="34-hour restart",
        )
        stops.append(
            Stop(
                type="restart",
                lat=None,
                lng=None,
                label=location or "Restart",
                arrival=segments[-1].start,
                duration_hours=_hours(RESTART_DURATION_MIN),
                note="34-hour restart",
            )
        )
        state.cycle_used = 0
        _reset_after_rest(state)
        restarts += 1
    return restarts


def _insert_rest(
    state: ClockState,
    segments: List[Segment],
    stops: List[Stop],
    location: str,
    lat: Optional[float],
    lng: Optional[float],
) -> None:
    _emit(
        segments,
        state,
        Status.SB,
        REST_DURATION_MIN,
        location=location,
        note="10-hour rest",
        lat=lat,
        lng=lng,
    )
    stops.append(
        Stop(
            type="rest",
            lat=lat,
            lng=lng,
            label=location or "Rest",
            arrival=segments[-1].start,
            duration_hours=_hours(REST_DURATION_MIN),
            note="10-hour rest",
        )
    )
    _reset_after_rest(state)


def _insert_break(
    state: ClockState,
    segments: List[Segment],
    stops: List[Stop],
    location: str,
    lat: Optional[float],
    lng: Optional[float],
) -> None:
    _emit(
        segments,
        state,
        Status.OFF,
        BREAK_DURATION_MIN,
        location=location,
        note="30-minute break",
        lat=lat,
        lng=lng,
    )
    # Break is OFF — does not count toward cycle or window pause (window still runs).
    # Window continues because wall time advanced.
    _ensure_window(state)
    state.driving_since_break = 0
    stops.append(
        Stop(
            type="break",
            lat=lat,
            lng=lng,
            label=location or "Break",
            arrival=segments[-1].start,
            duration_hours=_hours(BREAK_DURATION_MIN),
            note="30-minute break",
        )
    )


def _insert_fuel(
    state: ClockState,
    segments: List[Segment],
    stops: List[Stop],
    location: str,
    lat: Optional[float],
    lng: Optional[float],
) -> None:
    _emit(
        segments,
        state,
        Status.ON,
        FUEL_DURATION_MIN,
        location=location,
        note="Fuel stop",
        lat=lat,
        lng=lng,
    )
    _add_on_duty(state, FUEL_DURATION_MIN)
    # ≥30 min not driving → resets break clock
    state.driving_since_break = 0
    state.miles_since_fuel = 0.0
    stops.append(
        Stop(
            type="fuel",
            lat=lat,
            lng=lng,
            label=location or "Fuel",
            arrival=segments[-1].start,
            duration_hours=_hours(FUEL_DURATION_MIN),
            note="Fuel stop",
        )
    )


def _binding_drive_cap(state: ClockState, remaining_leg_min: int, miles_left_to_fuel: float, speed_mph: float) -> Tuple[int, str]:
    """
    Return (max_drive_minutes, reason) where reason is one of:
    drive | window | break | fuel | leg
    """
    caps = {
        "drive": max(0, DRIVE_LIMIT_MIN - state.driving_this_shift),
        "window": _window_remaining(state) if state.window_start else WINDOW_LIMIT_MIN,
        "break": max(0, BREAK_DRIVE_LIMIT_MIN - state.driving_since_break),
        "leg": remaining_leg_min,
    }
    if speed_mph > 0 and miles_left_to_fuel < float("inf"):
        hours_to_fuel = miles_left_to_fuel / speed_mph
        caps["fuel"] = max(0, int(hours_to_fuel * 60))
    else:
        caps["fuel"] = remaining_leg_min

    reason = min(caps, key=caps.get)
    return caps[reason], reason


def _interpolate_point(
    progress_ratio: float,
    start_lat: Optional[float],
    start_lng: Optional[float],
    end_lat: Optional[float],
    end_lng: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    if None in (start_lat, start_lng, end_lat, end_lng):
        return None, None
    r = max(0.0, min(1.0, progress_ratio))
    return (
        start_lat + (end_lat - start_lat) * r,
        start_lng + (end_lng - start_lng) * r,
    )


def plan_trip(
    work_items: List[WorkItem],
    cycle_used_hours: float,
    start_datetime: datetime,
    stop_locator=None,
) -> PlanResult:
    """
    Plan a legal schedule for the given work queue.

    stop_locator(kind, miles_along_drive_so_far, drive_hours_so_far) -> (lat, lng, label)
    is optional; used for mid-route break/rest/fuel coordinates.
    """
    state = ClockState(
        now=start_datetime,
        cycle_used=int(round(cycle_used_hours * 60)),
    )
    cycle_start = state.cycle_used
    segments: List[Segment] = []
    stops: List[Stop] = []
    restarts_taken = 0

    # Track cumulative drive for stop placement across the whole trip.
    cum_drive_min = 0
    cum_drive_miles = 0.0

    for item in work_items:
        if item.kind == "on_duty":
            restarts_taken += _maybe_restart(state, segments, stops, item.location)
            minutes = int(round(item.duration_hours * 60))
            note_lower = (item.note or "").lower()
            stop_type = "pickup" if "pickup" in note_lower else "dropoff" if "dropoff" in note_lower or "drop-off" in note_lower else "on_duty"

            _emit(
                segments,
                state,
                Status.ON,
                minutes,
                location=item.location,
                note=item.note,
                lat=item.lat,
                lng=item.lng,
            )
            _add_on_duty(state, minutes)
            # ≥30 min not driving resets break
            if minutes >= BREAK_DURATION_MIN:
                state.driving_since_break = 0

            stops.append(
                Stop(
                    type=stop_type if stop_type in ("pickup", "dropoff") else "pickup",
                    lat=item.lat,
                    lng=item.lng,
                    label=item.location or item.note,
                    arrival=segments[-1].start,
                    duration_hours=_hours(minutes),
                    note=item.note,
                )
            )
            continue

        if item.kind != "drive":
            raise ValueError(f"Unknown work item kind: {item.kind}")

        remaining_min = int(round(item.duration_hours * 60))
        remaining_miles = float(item.distance_miles)
        speed_mph = (remaining_miles / (remaining_min / 60.0)) if remaining_min > 0 else 55.0
        if speed_mph <= 0:
            speed_mph = 55.0

        leg_start_miles = cum_drive_miles
        leg_total_miles = remaining_miles or 1.0
        leg_start_min = cum_drive_min
        leg_total_min = remaining_min or 1

        while remaining_min > 0:
            restarts_taken += _maybe_restart(state, segments, stops, item.location)

            # If already at a hard limit with zero drive allowance, insert the required stop first.
            if state.driving_this_shift >= DRIVE_LIMIT_MIN or _window_remaining(state) <= 0:
                progress = (cum_drive_miles - leg_start_miles) / leg_total_miles
                lat, lng = _interpolate_point(progress, None, None, item.lat, item.lng)
                if stop_locator:
                    lat, lng, label = stop_locator("rest", cum_drive_miles, cum_drive_min / 60.0)
                else:
                    label = item.location or "Rest stop"
                _insert_rest(state, segments, stops, label, lat, lng)
                continue

            if state.driving_since_break >= BREAK_DRIVE_LIMIT_MIN:
                progress = (cum_drive_miles - leg_start_miles) / leg_total_miles
                lat, lng = _interpolate_point(progress, None, None, item.lat, item.lng)
                if stop_locator:
                    lat, lng, label = stop_locator("break", cum_drive_miles, cum_drive_min / 60.0)
                else:
                    label = item.location or "Break"
                _insert_break(state, segments, stops, label, lat, lng)
                continue

            miles_to_fuel = max(0.0, FUEL_INTERVAL_MILES - state.miles_since_fuel)
            drive_min, reason = _binding_drive_cap(state, remaining_min, miles_to_fuel, speed_mph)

            if drive_min <= 0:
                # Degenerate: force the binding stop.
                if reason == "fuel" or state.miles_since_fuel >= FUEL_INTERVAL_MILES:
                    progress = (cum_drive_miles - leg_start_miles) / leg_total_miles
                    lat, lng = _interpolate_point(progress, None, None, item.lat, item.lng)
                    if stop_locator:
                        lat, lng, label = stop_locator("fuel", cum_drive_miles, cum_drive_min / 60.0)
                    else:
                        label = item.location or "Fuel"
                    _insert_fuel(state, segments, stops, label, lat, lng)
                elif reason in ("drive", "window"):
                    progress = (cum_drive_miles - leg_start_miles) / leg_total_miles
                    lat, lng = _interpolate_point(progress, None, None, item.lat, item.lng)
                    if stop_locator:
                        lat, lng, label = stop_locator("rest", cum_drive_miles, cum_drive_min / 60.0)
                    else:
                        label = item.location or "Rest stop"
                    _insert_rest(state, segments, stops, label, lat, lng)
                else:
                    progress = (cum_drive_miles - leg_start_miles) / leg_total_miles
                    lat, lng = _interpolate_point(progress, None, None, item.lat, item.lng)
                    if stop_locator:
                        lat, lng, label = stop_locator("break", cum_drive_miles, cum_drive_min / 60.0)
                    else:
                        label = item.location or "Break"
                    _insert_break(state, segments, stops, label, lat, lng)
                continue

            miles_this = min(remaining_miles, speed_mph * (drive_min / 60.0)) if remaining_miles else 0.0
            # Align miles with minutes if we're finishing the leg
            if drive_min >= remaining_min:
                drive_min = remaining_min
                miles_this = remaining_miles
                reason = "leg"

            _emit(
                segments,
                state,
                Status.D,
                drive_min,
                location=item.location,
                note=item.note or "Driving",
            )
            _add_driving(state, drive_min, miles_this)
            remaining_min -= drive_min
            remaining_miles = max(0.0, remaining_miles - miles_this)
            cum_drive_min += drive_min
            cum_drive_miles += miles_this

            if reason == "leg" or remaining_min <= 0:
                break

            progress = (cum_drive_miles - leg_start_miles) / leg_total_miles
            lat, lng = _interpolate_point(progress, None, None, item.lat, item.lng)

            if reason == "fuel":
                if stop_locator:
                    lat, lng, label = stop_locator("fuel", cum_drive_miles, cum_drive_min / 60.0)
                else:
                    label = item.location or "Fuel"
                _insert_fuel(state, segments, stops, label, lat, lng)
            elif reason == "break":
                if stop_locator:
                    lat, lng, label = stop_locator("break", cum_drive_miles, cum_drive_min / 60.0)
                else:
                    label = item.location or "Break"
                _insert_break(state, segments, stops, label, lat, lng)
            elif reason in ("drive", "window"):
                if stop_locator:
                    lat, lng, label = stop_locator("rest", cum_drive_miles, cum_drive_min / 60.0)
                else:
                    label = item.location or "Rest stop"
                _insert_rest(state, segments, stops, label, lat, lng)

    return PlanResult(
        segments=segments,
        stops=stops,
        cycle_used_start=_hours(cycle_start),
        cycle_used_end=_hours(state.cycle_used),
        restarts_taken=restarts_taken,
    )
