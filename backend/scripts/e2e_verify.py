"""End-to-end API verification against a running server."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE = "http://127.0.0.1:8000"


def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"detail": body}
        return e.code, parsed


def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode())


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def validate_trip(body, *, expect_days_min=1, expect_restart=False, expect_fuel=False):
    assert_true("id" in body, "missing id")
    assert_true("route" in body, "missing route")
    assert_true(len(body["route"]["geometry"]) >= 2, "geometry too short")
    assert_true(body["route"]["total_distance_miles"] > 0, "distance should be > 0")
    assert_true("stops" in body and len(body["stops"]) >= 2, "need pickup/dropoff stops")
    types = {s["type"] for s in body["stops"]}
    assert_true("pickup" in types, f"missing pickup in {types}")
    assert_true("dropoff" in types, f"missing dropoff in {types}")
    if expect_fuel:
        assert_true("fuel" in types, f"expected fuel stop, got {types}")
    if expect_restart:
        assert_true(
            body["summary"]["restarts_taken"] >= 1 or "restart" in types,
            "expected 34h restart",
        )

    days = body["days"]
    assert_true(len(days) >= expect_days_min, f"expected >= {expect_days_min} days, got {len(days)}")
    for d in days:
        total = round(sum(d["totals"].values()), 2)
        assert_true(abs(total - 24.0) < 0.05, f"day {d['date']} totals {total}, not 24")
        assert_true(len(d["segments"]) > 0, f"day {d['date']} has no segments")
        for key in ("OFF", "SB", "D", "ON"):
            assert_true(key in d["totals"], f"missing total {key}")
        assert_true("miles_driving" in d, "missing miles_driving")
        assert_true("remarks" in d, "missing remarks")
        assert_true("recap" in d, "missing recap")
        assert_true("on_duty_today" in d["recap"], "missing recap.on_duty_today")

    # statuses only legal codes
    for d in days:
        for seg in d["segments"]:
            assert_true(seg["status"] in ("OFF", "SB", "D", "ON"), f"bad status {seg['status']}")
            assert_true(seg["start"] < seg["end"], "segment start >= end")


def main():
    failures = []

    def run(name, fn):
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as e:
            failures.append((name, e))
            print(f"FAIL  {name}: {e}")

    def t_health():
        code, body = get("/api/health/")
        assert_true(code == 200 and body.get("status") == "ok", body)

    def t_happy_path():
        code, body = post(
            "/api/trips/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Des Moines, IA",
                "dropoff_location": "Denver, CO",
                "current_cycle_used": 12.5,
                "start_datetime": "2026-07-23T06:00:00",
            },
        )
        assert_true(code == 201, f"status {code}: {body}")
        validate_trip(body, expect_days_min=2)
        assert_true(body["summary"]["total_days"] == len(body["days"]), "total_days mismatch")
        print(
            f"       -> {body['route']['total_distance_miles']} mi, "
            f"{body['summary']['total_days']} days, "
            f"{len(body['stops'])} stops, types={sorted({s['type'] for s in body['stops']})}"
        )

    def t_short_trip():
        code, body = post(
            "/api/trips/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Naperville, IL",
                "dropoff_location": "Aurora, IL",
                "current_cycle_used": 5,
                "start_datetime": "2026-07-23T08:00:00",
            },
        )
        assert_true(code == 201, f"status {code}: {body}")
        validate_trip(body, expect_days_min=1)
        assert_true(body["summary"]["restarts_taken"] == 0, "unexpected restart on short trip")

    def t_cycle_restart():
        code, body = post(
            "/api/trips/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Des Moines, IA",
                "dropoff_location": "Denver, CO",
                "current_cycle_used": 68,
                "start_datetime": "2026-07-23T06:00:00",
            },
        )
        assert_true(code == 201, f"status {code}: {body}")
        validate_trip(body, expect_days_min=2, expect_restart=True)
        print(f"       -> restarts={body['summary']['restarts_taken']}")

    def t_long_fuel():
        # LA is far — should fuel
        code, body = post(
            "/api/trips/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Kansas City, MO",
                "dropoff_location": "Los Angeles, CA",
                "current_cycle_used": 0,
                "start_datetime": "2026-07-23T05:00:00",
            },
        )
        assert_true(code == 201, f"status {code}: {body}")
        validate_trip(body, expect_days_min=2, expect_fuel=body["route"]["total_distance_miles"] >= 1000)
        print(
            f"       -> {body['route']['total_distance_miles']} mi, "
            f"fuel stops={sum(1 for s in body['stops'] if s['type']=='fuel')}"
        )

    def t_invalid_location():
        code, body = post(
            "/api/trips/",
            {
                "current_location": "zzzznotacityxyz123",
                "pickup_location": "Des Moines, IA",
                "dropoff_location": "Denver, CO",
                "current_cycle_used": 10,
            },
        )
        assert_true(code in (400, 502), f"expected error status, got {code}: {body}")
        assert_true("detail" in body, "error should include detail")
        detail = str(body["detail"]).lower()
        assert_true(
            "could not find" in detail or "location" in detail or "routing" in detail,
            f"unfriendly error: {body}",
        )

    def t_validation():
        code, body = post(
            "/api/trips/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Des Moines, IA",
                "dropoff_location": "Denver, CO",
                "current_cycle_used": 99,
            },
        )
        assert_true(code == 400, f"expected 400 for cycle>70, got {code}: {body}")

    def t_midnight():
        code, body = post(
            "/api/trips/",
            {
                "current_location": "Chicago, IL",
                "pickup_location": "Joliet, IL",
                "dropoff_location": "Bloomington, IL",
                "current_cycle_used": 0,
                "start_datetime": "2026-07-23T22:30:00",
            },
        )
        assert_true(code == 201, f"status {code}: {body}")
        validate_trip(body, expect_days_min=1)
        # if drive crosses midnight, >=2 days
        if len(body["days"]) >= 2:
            for d in body["days"]:
                assert_true(abs(sum(d["totals"].values()) - 24) < 0.05, "midnight totals")

    run("health", t_health)
    run("happy path Chicago→Denver", t_happy_path)
    run("short local trip", t_short_trip)
    run("cycle restart at 68h", t_cycle_restart)
    run("long trip fuel", t_long_fuel)
    run("invalid location", t_invalid_location)
    run("validation cycle>70", t_validation)
    run("near-midnight start", t_midnight)

    print()
    if failures:
        print(f"{len(failures)} FAILED")
        for name, err in failures:
            print(f" - {name}: {err}")
        sys.exit(1)
    print("ALL E2E CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
