from django.urls import path

from . import views

app_name = "radar"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("buscar/", views.busca, name="busca"),
    path("api/sugestoes/", views.sugestoes, name="sugestoes"),
    path("regiao/<slug:slug>/", views.regiao, name="regiao"),
    path("comparar/", views.comparar, name="comparar"),
    path("regiao/<slug:slug>/pontos.geojson", views.pontos_regiao, name="pontos_regiao"),
    path("cep/<str:cep>/", views.cep, name="cep"),
    path("transacao/<int:id>/", views.transacao, name="transacao"),
    path("entrar/", views.entrar, name="entrar"),
]
