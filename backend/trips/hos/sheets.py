"""Split duty segments into calendar-day log sheets with 24.00 totals."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from .engine import Segment


def _minutes(td: timedelta) -> int:
    return int(td.total_seconds() // 60)


def _day_start(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, dt.day, tzinfo=dt.tzinfo)


def split_into_days(segments: List[Segment]) -> List[dict]:
    """
    Split segments at midnight. Each day returns:
      { date, segments, totals: {OFF, SB, D, ON} }
    Totals are in hours and must sum to 24.00 for complete days.
    Partial first/last days still sum to the covered duration.
    """
    if not segments:
        return []

    # Expand segments across midnight boundaries.
    pieces: List[Segment] = []
    for seg in segments:
        cursor = seg.start
        while cursor.date() < seg.end.date():
            nxt = _day_start(cursor) + timedelta(days=1)
            pieces.append(
                Segment(
                    start=cursor,
                    end=nxt,
                    status=seg.status,
                    location=seg.location,
                    note=seg.note,
                    lat=seg.lat,
                    lng=seg.lng,
                )
            )
            cursor = nxt
        if cursor < seg.end:
            pieces.append(
                Segment(
                    start=cursor,
                    end=seg.end,
                    status=seg.status,
                    location=seg.location,
                    note=seg.note,
                    lat=seg.lat,
                    lng=seg.lng,
                )
            )

    # Group by date
    by_date: Dict[str, List[Segment]] = {}
    for p in pieces:
        key = p.start.date().isoformat()
        by_date.setdefault(key, []).append(p)

    days = []
    for date_key in sorted(by_date.keys()):
        day_segs = by_date[date_key]
        totals_min = {"OFF": 0, "SB": 0, "D": 0, "ON": 0}
        for s in day_segs:
            totals_min[s.status] = totals_min.get(s.status, 0) + _minutes(s.end - s.start)

        # Pad incomplete calendar coverage with OFF so each sheet totals 24.00
        covered = sum(totals_min.values())
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
                covered += gap
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
                covered += gap

        totals = {
            k: round(v / 60.0, 2) for k, v in totals_min.items()
        }
        total_sum = round(sum(totals.values()), 2)
        assert abs(total_sum - 24.0) < 0.02, f"Day {date_key} totals {total_sum}, expected 24.00"

        days.append(
            {
                "date": date_key,
                "segments": [s.to_dict() for s in padded],
                "totals": totals,
            }
        )

    return days
