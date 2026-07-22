"""HOS engine unit tests — run before UI work."""

from datetime import datetime
from django.test import SimpleTestCase

from trips.hos.engine import WorkItem, plan_trip
from trips.hos.sheets import split_into_days


def _drive(hours, miles=None, location="Somewhere"):
    return WorkItem(
        kind="drive",
        duration_hours=hours,
        distance_miles=miles if miles is not None else hours * 55,
        note="Driving",
        location=location,
        lat=40.0,
        lng=-90.0,
    )


def _on(hours, note, location="Depot"):
    return WorkItem(
        kind="on_duty",
        duration_hours=hours,
        note=note,
        location=location,
        lat=41.0,
        lng=-91.0,
    )


class HosEngineTests(SimpleTestCase):
    def test_short_trip_no_rest_no_break(self):
        # 4 hrs driving + pickup/dropoff; cycle 10
        work = [
            _drive(2.0, 110),
            _on(1.0, "Pickup"),
            _drive(2.0, 110),
            _on(1.0, "Dropoff"),
        ]
        plan = plan_trip(work, cycle_used_hours=10.0, start_datetime=datetime(2026, 7, 23, 6, 0))
        statuses = [s.status for s in plan.segments]
        self.assertNotIn("SB", statuses)
        self.assertFalse(any(s.note == "30-minute break" for s in plan.segments))
        days = split_into_days(plan.segments)
        self.assertEqual(len(days), 1)
        self.assertAlmostEqual(sum(days[0]["totals"].values()), 24.0, places=1)

    def test_thirteen_hours_triggers_break_and_rest(self):
        # Pure 13h drive to exercise 8h break + 11h rest
        work = [_drive(13.0, 715)]
        plan = plan_trip(work, cycle_used_hours=10.0, start_datetime=datetime(2026, 7, 23, 6, 0))
        notes = [s.note for s in plan.segments]
        self.assertTrue(any("break" in (n or "").lower() for n in notes))
        self.assertTrue(any(s.status == "SB" for s in plan.segments))
        days = split_into_days(plan.segments)
        self.assertGreaterEqual(len(days), 2)
        for d in days:
            self.assertAlmostEqual(sum(d["totals"].values()), 24.0, places=1)

    def test_fuel_stop_on_long_mileage(self):
        # 1400 miles at ~55 mph ≈ 25.45 hrs — will also hit rests; must have fuel
        work = [_drive(25.5, 1400)]
        plan = plan_trip(work, cycle_used_hours=0.0, start_datetime=datetime(2026, 7, 23, 6, 0))
        fuel_stops = [s for s in plan.stops if s.type == "fuel"]
        self.assertGreaterEqual(len(fuel_stops), 1)
        # After a fuel stop, the next segment should not be an immediate redundant break
        for i, seg in enumerate(plan.segments[:-1]):
            if seg.note == "Fuel stop":
                nxt = plan.segments[i + 1]
                self.assertNotEqual(nxt.note, "30-minute break")

    def test_cycle_exhaustion_inserts_restart(self):
        work = [
            _drive(8.0, 440),
            _on(1.0, "Pickup"),
            _drive(8.0, 440),
            _on(1.0, "Dropoff"),
        ]
        # 68 used + ~18 on-duty → needs restart
        plan = plan_trip(work, cycle_used_hours=68.0, start_datetime=datetime(2026, 7, 23, 6, 0))
        self.assertGreaterEqual(plan.restarts_taken, 1)
        self.assertTrue(any(s.type == "restart" for s in plan.stops))
        days = split_into_days(plan.segments)
        self.assertGreaterEqual(len(days), 2)
        for d in days:
            self.assertAlmostEqual(sum(d["totals"].values()), 24.0, places=1)

    def test_midnight_crossing_splits_cleanly(self):
        work = [_drive(6.0, 330)]
        plan = plan_trip(
            work,
            cycle_used_hours=0.0,
            start_datetime=datetime(2026, 7, 23, 22, 0),  # 10pm → crosses midnight
        )
        days = split_into_days(plan.segments)
        self.assertEqual(len(days), 2)
        for d in days:
            self.assertAlmostEqual(sum(d["totals"].values()), 24.0, places=1)
        # Driving appears on both sheets
        self.assertTrue(any(s["status"] == "D" for s in days[0]["segments"]))
        self.assertTrue(any(s["status"] == "D" for s in days[1]["segments"]))

    def test_every_sheet_totals_24(self):
        work = [
            _drive(9.0, 495),
            _on(1.0, "Pickup"),
            _drive(10.0, 550),
            _on(1.0, "Dropoff"),
        ]
        plan = plan_trip(work, cycle_used_hours=5.0, start_datetime=datetime(2026, 7, 23, 5, 30))
        for d in split_into_days(plan.segments):
            self.assertAlmostEqual(sum(d["totals"].values()), 24.0, places=1)

    def test_cycle_never_exceeds_seventy_without_restart(self):
        work = [
            _drive(6.0, 330),
            _on(1.0, "Pickup"),
            _drive(12.0, 660),
            _on(1.0, "Dropoff"),
        ]
        plan = plan_trip(work, cycle_used_hours=68.0, start_datetime=datetime(2026, 7, 23, 6, 0))
        self.assertGreaterEqual(plan.restarts_taken, 1)
        cycle = 68 * 60
        for seg in plan.segments:
            mins = int((seg.end - seg.start).total_seconds() // 60)
            if seg.note == "34-hour restart":
                self.assertGreaterEqual(cycle, 70 * 60)
                cycle = 0
                continue
            if seg.status in ("D", "ON"):
                self.assertLessEqual(cycle, 70 * 60)
                cycle += mins
                self.assertLessEqual(cycle, 70 * 60)

    def test_no_more_than_eight_hours_driving_without_break(self):
        work = [_drive(13.0, 715)]
        plan = plan_trip(work, cycle_used_hours=0.0, start_datetime=datetime(2026, 7, 23, 6, 0))
        streak = 0
        for seg in plan.segments:
            mins = int((seg.end - seg.start).total_seconds() // 60)
            if seg.status == "D":
                streak += mins
                self.assertLessEqual(streak, 8 * 60)
            elif mins >= 30:
                streak = 0

    def test_fourteen_hour_window_not_exceeded(self):
        work = [
            _drive(5.0, 275),
            _on(1.0, "Pickup"),
            _drive(9.0, 495),
            _on(1.0, "Dropoff"),
        ]
        plan = plan_trip(work, cycle_used_hours=0.0, start_datetime=datetime(2026, 7, 23, 6, 0))
        window_start = None
        for seg in plan.segments:
            if seg.note == "10-hour rest" or seg.note == "34-hour restart":
                window_start = None
                continue
            if seg.status in ("D", "ON", "OFF") and seg.note != "Before duty":
                # OFF break still inside window
                if window_start is None and seg.status in ("D", "ON"):
                    window_start = seg.start
                if window_start is not None and seg.status in ("D", "ON", "OFF"):
                    elapsed = (seg.end - window_start).total_seconds() / 3600.0
                    # Driving/ON must not end after window > 14h
                    if seg.status in ("D", "ON"):
                        self.assertLessEqual(elapsed, 14.02)
