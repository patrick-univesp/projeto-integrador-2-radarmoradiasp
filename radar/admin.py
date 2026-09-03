from django.contrib import admin

from radar.models import Transacao

admin.site.site_header = "Radar da Moradia SP · administração"
admin.site.site_title = "Radar da Moradia SP"
admin.site.index_title = "Painel"


@admin.register(Transacao)
class TransacaoAdmin(admin.ModelAdmin):
    """Só leitura — a edição não faz sentido, o dado vem inteiro da carga."""

    list_display = ("sql", "logradouro", "numero", "bairro_norm", "distrito",
                    "data_transacao", "valor_transacao", "rs_m2_construido", "geo_nivel", "qualidade")
    list_filter = ("qualidade", "geo_nivel", "flag_cadastro_defasado", "uso_grupo", "ano_transacao")
    search_fields = ("sql", "logradouro", "bairro_norm", "cep")
    list_per_page = 50
    ordering = ("-data_transacao",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
