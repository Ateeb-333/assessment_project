"""Split duty segments into calendar-day log sheets with 24.00 totals.

Aligned with FMCSA Interstate Truck Driver's Guide to Hours of Service
(April 2022) RODS requirements: graph grid, remarks at duty changes,
total hours (=24), total miles driving today, and a simplified 70/8 recap.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .engine import CYCLE_LIMIT_MIN, Segment


def _minutes(td: timedelta) -> int:
    return int(td.total_seconds() // 60)


def _day_start(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, dt.day, tzinfo=dt.tzinfo)


def _slice_segment(seg: Segment, start: datetime, end: datetime) -> Segment:
    """Proportion miles by duration when a drive segment is split at midnight."""
    full = _minutes(seg.end - seg.start) or 1
    part = _minutes(end - start)
    miles = (seg.miles * part / full) if seg.miles else 0.0
    return Segment(
        start=start,
        end=end,
        status=seg.status,
        location=seg.location,
        note=seg.note,
        lat=seg.lat,
        lng=seg.lng,
        miles=miles,
    )


def _remarks_for_day(segments: List[Segment]) -> List[dict]:
    """City/State (or note) at each change of duty — FMCSA remarks rule."""
    remarks = []
    last_status = None
    for seg in segments:
        if seg.note in ("Before duty", "After duty"):
            continue
        if seg.status == last_status:
            continue
        label = (seg.location or "").strip()
        if not label and seg.note:
            label = seg.note
        if not label:
            continue
        remarks.append(
            {
                "time": seg.start.isoformat(timespec="seconds"),
                "location": label,
                "status": seg.status if isinstance(seg.status, str) else str(seg.status),
                "note": seg.note or "",
            }
        )
        last_status = seg.status
    return remarks


def split_into_days(
    segments: List[Segment],
    *,
    cycle_used_start_hours: float = 0.0,
) -> List[dict]:
    """
    Split segments at midnight. Each day returns RODS-oriented fields:
      date, segments, totals, miles_driving, on_duty_today, remarks, recap
    """
    if not segments:
        return []

    pieces: List[Segment] = []
    for seg in segments:
        cursor = seg.start
        while cursor.date() < seg.end.date():
            nxt = _day_start(cursor) + timedelta(days=1)
            pieces.append(_slice_segment(seg, cursor, nxt))
            cursor = nxt
        if cursor < seg.end:
            pieces.append(_slice_segment(seg, cursor, seg.end))

    by_date: Dict[str, List[Segment]] = {}
    for p in pieces:
        key = p.start.date().isoformat()
        by_date.setdefault(key, []).append(p)

    # Track rolling cycle across days for recap (scalar model + 34h restart).
    cycle_min = int(round(cycle_used_start_hours * 60))
    days = []

    for date_key in sorted(by_date.keys()):
        day_segs = by_date[date_key]
        totals_min = {"OFF": 0, "SB": 0, "D": 0, "ON": 0}
        miles_driving = 0.0
        restarted_today = False

        for s in day_segs:
            status = s.status if isinstance(s.status, str) else str(s.status)
            totals_min[status] = totals_min.get(status, 0) + _minutes(s.end - s.start)
            if status == "D":
                miles_driving += s.miles or 0.0
            if s.note == "34-hour restart":
                restarted_today = True
                cycle_min = 0
            elif status in ("D", "ON"):
                cycle_min += _minutes(s.end - s.start)

        day_begin = _day_start(day_segs[0].start)
        day_end = day_begin + timedelta(days=1)
        trip_day_start = day_segs[0].start
        trip_day_end = day_segs[-1].end

        padded: List[Segment] = list(day_segs)
        if trip_day_start > day_begin:
            gap = _minutes(trip_day_start - day_begin)
            if gap > 0:
                padded.insert(
                    0,
                    Segment(
                        start=day_begin,
                        end=trip_day_start,
                        status="OFF",
                        location="",
                        note="Before duty",
                    ),
                )
                totals_min["OFF"] += gap
        if trip_day_end < day_end:
            gap = _minutes(day_end - trip_day_end)
            if gap > 0:
                padded.append(
                    Segment(
                        start=trip_day_end,
                        end=day_end,
                        status="OFF",
                        location="",
                        note="After duty",
                    )
                )
                totals_min["OFF"] += gap

        totals = {k: round(v / 60.0, 2) for k, v in totals_min.items()}
        total_sum = round(sum(totals.values()), 2)
        assert abs(total_sum - 24.0) < 0.02, f"Day {date_key} totals {total_sum}, expected 24.00"

        on_duty_today = round(totals["D"] + totals["ON"], 2)
        # Recap A ≈ on-duty in current 8-day window (our scalar cycle at end of day)
        a_hours = round(cycle_min / 60.0, 2)
        if restarted_today:
            # After a valid 34h restart, full 70 are available again going forward.
            b_hours = round(70.0 - a_hours, 2)
        else:
            b_hours = round(max(0.0, 70.0 - a_hours), 2)

        days.append(
            {
                "date": date_key,
                "segments": [s.to_dict() for s in padded],
                "totals": totals,
                "miles_driving": round(miles_driving, 1),
                "miles_today": round(miles_driving, 1),  # same under our model
                "on_duty_today": on_duty_today,
                "remarks": _remarks_for_day(padded),
                "recap": {
                    "on_duty_today": on_duty_today,
                    "a_hours_last_8_incl_today": a_hours,
                    "b_hours_available_tomorrow": b_hours,
                    "c_hours_last_8_incl_today": a_hours,
                    "restart_taken_today": restarted_today,
                    "note": (
                        "If you took 34 consecutive hours off duty you have 70 hours available."
                        if restarted_today
                        else "70-hour / 8-day property-carrying schedule (scalar cycle input)."
                    ),
                },
            }
        )

    return days
