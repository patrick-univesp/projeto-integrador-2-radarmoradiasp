from django.db import models


class Transacao(models.Model):
    """Transação imobiliária registrada numa guia de ITBI paga.

    Esquema, origem de cada campo e regras de correção: ``docs/modelo-transacao.md``.
    """

    sql = models.CharField("SQL", max_length=11)

    logradouro = models.CharField(max_length=150)
    numero = models.CharField(max_length=10)
    complemento = models.CharField(max_length=40, blank=True)
    bairro = models.CharField(max_length=120, blank=True)
    bairro_norm = models.CharField(max_length=120, blank=True, db_index=True)
    cep = models.CharField(max_length=8, blank=True, db_index=True)
    distrito = models.CharField(max_length=60, blank=True, db_index=True)

    lat = models.FloatField(null=True)
    lon = models.FloatField(null=True)
    geo_nivel = models.CharField(max_length=2, blank=True)

    valor_transacao = models.DecimalField(max_digits=15, decimal_places=2)
    base_calculo = models.DecimalField(max_digits=15, decimal_places=2)
    data_transacao = models.DateField(null=True)
    ano_transacao = models.IntegerField(null=True, db_index=True)

    area_construida = models.DecimalField(max_digits=9, decimal_places=2, null=True)
    uso_grupo = models.CharField(max_length=40, blank=True, db_index=True)

    rs_m2_construido = models.DecimalField(max_digits=12, decimal_places=2, null=True)

    qualidade = models.SmallIntegerField(default=0, db_index=True)
    flag_cadastro_defasado = models.BooleanField(default=False)

    # Mês/ano em que a guia foi paga (o nome da aba mensal da planilha) — não é o
    # do negócio (esse é data_transacao). É a chave da carga: recarregar um mês
    # substitui só as linhas daquele mes_guia+ano.
    ano_guia = models.SmallIntegerField(null=True)
    mes_guia = models.SmallIntegerField(null=True)

    class Meta:
        verbose_name = "transação"
        verbose_name_plural = "transações"
        indexes = [
            models.Index(fields=["lat", "lon"], name="radar_trans_lat_lon"),
            models.Index(fields=["distrito", "ano_transacao"], name="radar_trans_distrito_ano"),
            models.Index(fields=["bairro_norm", "ano_transacao"], name="radar_trans_bairro_ano"),
            models.Index(fields=["ano_guia", "mes_guia"], name="radar_trans_guia"),
        ]

    def __str__(self):
        return f"{self.sql} — {self.data_transacao or 's/ data'}"
