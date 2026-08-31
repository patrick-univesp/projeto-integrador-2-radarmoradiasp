from django.urls import path

from . import views

app_name = "radar"

urlpatterns = [
    path("", views.inicio, name="inicio"),
]
