from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from radar.admin_carga import (
    FormularioCarga,
    carga_em_andamento,
    iniciar_carga,
    reconciliar_orfas,
)
from radar.models import CargaMensal, Transacao

admin.site.site_header = "Radar da Moradia SP · administração"
admin.site.site_title = "Radar da Moradia SP"
admin.site.index_title = "Painel"


@admin.register(Transacao)
class TransacaoAdmin(admin.ModelAdmin):
    """Só leitura — a edição não faz sentido, o dado vem inteiro da carga."""

    list_display = ("sql", "logradouro", "numero", "bairro_norm", "distrito",
                    "data_transacao", "valor_transacao", "rs_m2_construido", "geo_nivel", "qualidade")
    # ano_guia/mes_guia primeiro: filtrar por eles mostra a contagem do mês no topo
    # da lista, para reconciliar com a planilha.
    list_filter = ("ano_guia", "mes_guia", "qualidade", "geo_nivel",
                   "flag_cadastro_defasado", "uso_grupo", "ano_transacao")
    search_fields = ("sql", "logradouro", "bairro_norm", "cep")
    list_per_page = 50
    ordering = ("-data_transacao",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CargaMensal)
class CargaMensalAdmin(admin.ModelAdmin):
    """Histórico das cargas de planilha. A carga em si roda na tela `Carregar
    planilha` (botão no topo da lista)."""

    change_list_template = "admin/radar/cargamensal/change_list.html"
    list_display = ("arquivo_nome", "status", "linhas_lidas", "linhas_gravadas",
                    "linhas_descartadas", "sem_geo", "pico_mb", "iniciado_em", "terminado_em")
    list_filter = ("status",)
    date_hierarchy = "iniciado_em"
    readonly_fields = ("resumo_por_mes",)

    def get_queryset(self, request):
        reconciliar_orfas()  # carga cuja thread morreu fica presa em "rodando"
        return super().get_queryset(request)

    @admin.display(
        description="Por mês da guia (lidas / gravadas / descartadas / qual!=0 / sem geo / sem região)"
    )
    def resumo_por_mes(self, obj):
        if not obj.por_mes:
            return "—"
        corpo = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>",
            (
                (k, m["lidas"], m["gravadas"], m["descartadas"], m["ruins"], m["sem_geo"],
                 m.get("sem_regiao", 0))
                for k, m in sorted(obj.por_mes.items())
            ),
        )
        return format_html("<table><tbody>{}</tbody></table>", corpo)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_urls(self):
        extra = [path("carregar/", self.admin_site.admin_view(self.carregar_view),
                      name="radar_cargamensal_carregar")]
        return extra + super().get_urls()

    def carregar_view(self, request):
        if request.method == "POST":
            form = FormularioCarga(request.POST, request.FILES)
            if carga_em_andamento():
                messages.error(request, "Já há uma carga em andamento. Espere ela terminar.")
            elif form.is_valid():
                carga = iniciar_carga(
                    form.cleaned_data["arquivo"], form.cleaned_data["abas"],
                    form.cleaned_data["substituir_mes"], request.user,
                )
                messages.success(request, "Carga iniciada. O progresso aparece abaixo.")
                return redirect(reverse("admin:radar_cargamensal_change", args=[carga.pk]))
        else:
            form = FormularioCarga()
        return render(request, "admin/radar/cargamensal/carregar.html", {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Carregar planilha",
            "em_andamento": carga_em_andamento(),
        })
