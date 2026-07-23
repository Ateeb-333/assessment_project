from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def root(_request):
    return JsonResponse(
        {
            "service": "eld-trip-planner",
            "status": "ok",
            "endpoints": {
                "health": "/api/health/",
                "create_trip": "POST /api/trips/",
            },
        }
    )


urlpatterns = [
    path("", root, name="root"),
    path("admin/", admin.site.urls),
    path("api/", include("trips.urls")),
]
