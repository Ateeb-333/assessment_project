from __future__ import annotations

from datetime import datetime, timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .hos import WorkItem, plan_trip, split_into_days
from .hos.geometry import build_cumulative, point_at_hours, point_at_miles
from .models import Trip
from .serializers import TripCreateSerializer
from .services.routing import RoutingError, geocode, reverse_geocode, route


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok", "service": "eld-trip-planner"})


class TripCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        ser = TripCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        start_dt = data.get("start_datetime")
        if start_dt is None:
            start_dt = datetime.now(timezone.utc)
        elif start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        try:
            current = geocode(data["current_location"])
            pickup = geocode(data["pickup_location"])
            dropoff = geocode(data["dropoff_location"])
            routed = route([current, pickup, dropoff])
        except RoutingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {"detail": f"Routing failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        legs = routed["legs"]
        if len(legs) < 2:
            return Response(
                {"detail": "Could not build a two-leg route"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        leg_a, leg_b = legs[0], legs[1]
        geometry = [(p[0], p[1]) for p in routed["geometry"]]
        cum_miles, cum_hours, coords = build_cumulative(
            geometry, routed["total_drive_hours"]
        )

        def stop_locator(kind, miles_along, drive_hours_along):
            if kind == "fuel":
                lat, lng = point_at_miles(cum_miles, coords, miles_along)
            else:
                lat, lng = point_at_hours(cum_hours, coords, drive_hours_along)
            try:
                label = reverse_geocode(lat, lng)
            except Exception:
                label = f"{lat:.3f}, {lng:.3f}"
            return lat, lng, label

        work = [
            WorkItem(
                kind="drive",
                duration_hours=leg_a["duration_hours"],
                distance_miles=leg_a["distance_miles"],
                note="Current → Pickup",
                location=data["pickup_location"],
                lat=pickup[0],
                lng=pickup[1],
            ),
            WorkItem(
                kind="on_duty",
                duration_hours=1.0,
                note="Pickup",
                location=data["pickup_location"],
                lat=pickup[0],
                lng=pickup[1],
            ),
            WorkItem(
                kind="drive",
                duration_hours=leg_b["duration_hours"],
                distance_miles=leg_b["distance_miles"],
                note="Pickup → Dropoff",
                location=data["dropoff_location"],
                lat=dropoff[0],
                lng=dropoff[1],
            ),
            WorkItem(
                kind="on_duty",
                duration_hours=1.0,
                note="Dropoff",
                location=data["dropoff_location"],
                lat=dropoff[0],
                lng=dropoff[1],
            ),
        ]

        # Use naive local-style timestamps for log sheets (single TZ assumption)
        naive_start = start_dt.replace(tzinfo=None)
        plan = plan_trip(
            work,
            cycle_used_hours=float(data["current_cycle_used"]),
            start_datetime=naive_start,
            stop_locator=stop_locator,
        )
        days = split_into_days(plan.segments)

        # Enrich mid-route stops that lack coords
        for stop in plan.stops:
            if stop.lat is None and stop.type in ("break", "rest", "fuel", "restart"):
                # leave as-is; locator usually filled them
                pass

        result = {
            "route": {
                "geometry": routed["geometry"],
                "total_distance_miles": routed["total_distance_miles"],
                "total_drive_hours": routed["total_drive_hours"],
            },
            "stops": [s.to_dict() for s in plan.stops],
            "days": days,
            "summary": {
                "cycle_used_start": plan.cycle_used_start,
                "cycle_used_end": plan.cycle_used_end,
                "restarts_taken": plan.restarts_taken,
                "total_days": len(days),
            },
            "waypoints": {
                "current": {"lat": current[0], "lng": current[1], "label": data["current_location"]},
                "pickup": {"lat": pickup[0], "lng": pickup[1], "label": data["pickup_location"]},
                "dropoff": {"lat": dropoff[0], "lng": dropoff[1], "label": data["dropoff_location"]},
            },
        }

        trip = Trip.objects.create(
            current_location=data["current_location"],
            pickup_location=data["pickup_location"],
            dropoff_location=data["dropoff_location"],
            current_cycle_used=data["current_cycle_used"],
            start_datetime=start_dt,
            result=result,
        )

        return Response({"id": trip.id, **result}, status=status.HTTP_201_CREATED)
