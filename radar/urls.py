from django.urls import path

from . import views

app_name = "radar"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("buscar/", views.busca, name="busca"),
    path("regiao/<slug:slug>/", views.regiao, name="regiao"),
    path("entrar/", views.entrar, name="entrar"),
]
