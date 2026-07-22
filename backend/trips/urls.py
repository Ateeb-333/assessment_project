from django.urls import path

from .views import HealthView, TripCreateView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("trips/", TripCreateView.as_view(), name="trip-create"),
]
