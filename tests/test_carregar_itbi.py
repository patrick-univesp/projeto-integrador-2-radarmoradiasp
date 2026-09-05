"""Carga ponta a ponta com a amostra sintética tests/dados/amostra_itbi.xlsx."""

import datetime as dt
from pathlib import Path

import openpyxl
import pytest
from django.core.management.base import CommandError

from radar.management.commands import carregar_itbi as cmd
from radar.management.commands.carregar_itbi import carregar
from radar.models import Transacao
from tests.dados.gerar_amostra_itbi import CABECALHO

XLSX = Path(__file__).parent / "dados" / "amostra_itbi.xlsx"
GEO = Path(__file__).parent / "dados" / "dados_geo_amostra"


def _carregar(**kw):
    return carregar(str(XLSX), base_dir_geo=str(GEO), blocos=3, **kw)


@pytest.mark.django_db
def test_carrega_todas_as_linhas():
    r = _carregar()
    assert r["total"]["lidas"] == 12
    assert r["total"]["gravadas"] == 12
    assert Transacao.objects.count() == 12


@pytest.mark.django_db
def test_cep_preserva_zero_a_esquerda():
    _carregar()
    assert Transacao.objects.filter(cep="05662000").exists()


@pytest.mark.django_db
def test_nenhum_rs_m2_zero():
    _carregar()
    assert not Transacao.objects.filter(rs_m2_construido=0).exists()
    zerada = Transacao.objects.get(valor_transacao=500000, base_calculo=0)
    assert zerada.rs_m2_construido is None
    assert zerada.qualidade != 0


@pytest.mark.django_db
def test_bairro_vazio_e_lixo_viram_bairro_norm_vazio():
    _carregar()
    assert Transacao.objects.filter(bairro="", bairro_norm="").count() == 1
    assert Transacao.objects.get(bairro="TORRE 2").bairro_norm == ""


@pytest.mark.django_db
def test_grafia_aglutinada_normaliza():
    _carregar()
    assert Transacao.objects.get(bairro="ITAIMBIBI").bairro_norm == "ITAIM BIBI"


@pytest.mark.django_db
def test_geo_por_lookup_cobre_a_escada():
    _carregar()
    t1 = Transacao.objects.get(sql="00103604280", numero="391")
    assert (t1.geo_nivel, t1.distrito) == ("T1", "REPUBLICA")
    t3 = Transacao.objects.get(sql="00102302388")
    assert (t3.geo_nivel, t3.distrito) == ("T3", "SE")
    sem = Transacao.objects.get(sql="99912300010")
    assert (sem.geo_nivel, sem.distrito) == ("--", "")  # sem match: entra, não é pulada


@pytest.mark.django_db
def test_distrito_slug_e_preenchido_pelo_registro_de_regioes():
    _carregar()
    t1 = Transacao.objects.get(sql="00103604280", numero="391")
    assert (t1.distrito, t1.distrito_slug) == ("REPUBLICA", "republica")
    t3 = Transacao.objects.get(sql="00102302388")
    assert (t3.distrito, t3.distrito_slug) == ("SE", "se")
    sem = Transacao.objects.get(sql="99912300010")
    assert (sem.distrito, sem.distrito_slug) == ("", "")  # sem geo, também sem região


@pytest.mark.django_db
def test_flag_cadastro_defasado():
    _carregar()
    assert Transacao.objects.get(sql="16526701080", complemento="BL A AP 71").flag_cadastro_defasado
    assert not Transacao.objects.get(sql="00103604280", numero="391").flag_cadastro_defasado


@pytest.mark.django_db
def test_multi_ano_e_reconciliacao_por_mes():
    r = _carregar()
    # abas de anos diferentes entram normalmente
    assert Transacao.objects.filter(ano_guia=2025, mes_guia=3).count() == 2
    assert Transacao.objects.filter(ano_guia=2026, mes_guia=1).count() == 8
    # ano_transacao (negócio) é independente do ano da guia
    antiga = Transacao.objects.get(valor_transacao=90000)
    assert (antiga.ano_transacao, antiga.ano_guia, antiga.mes_guia) == (1997, 2026, 2)
    # o resumo traz a quebra por mês para bater com a planilha
    assert r["por_mes"]["2025-03"]["lidas"] == 2
    assert r["por_mes"]["2025-03"]["gravadas"] == 2
    assert r["por_mes"]["2026-01"]["lidas"] == 8


@pytest.mark.django_db
def test_substituir_mes_e_idempotente():
    _carregar()
    _carregar(substituir_mes=True)
    assert Transacao.objects.count() == 12


@pytest.mark.django_db
def test_dry_run_nao_grava():
    r = _carregar(dry_run=True)
    assert r["total"]["lidas"] == 12
    assert Transacao.objects.count() == 0


def _tem_estatisticas_de(tabela):
    """``sqlite_stat1`` só existe depois do primeiro ``ANALYZE`` — sem checar a
    existência da tabela primeiro, a consulta falharia com "no such table" numa
    base que nunca rodou ANALYZE."""
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sqlite_stat1'")
        if not cur.fetchone()[0]:
            return False
        cur.execute("SELECT COUNT(*) FROM sqlite_stat1 WHERE tbl=%s", [tabela])
        return cur.fetchone()[0] > 0


@pytest.mark.django_db
def test_carga_de_verdade_atualiza_estatisticas_do_otimizador():
    """Achado real: sem ``ANALYZE``, o otimizador do SQLite escolhe o índice
    errado pra uma região sem nenhuma transação (o de ``qualidade``, que cobre
    quase toda a tabela, em vez do de ``distrito_slug``) — ~230ms por página
    contra ~15ms depois do fix. Roda de novo a cada carga porque a distribuição
    muda."""
    assert not _tem_estatisticas_de("radar_transacao")
    _carregar()
    assert _tem_estatisticas_de("radar_transacao")


@pytest.mark.django_db
def test_dry_run_nao_atualiza_estatisticas_do_otimizador():
    _carregar(dry_run=True)
    assert not _tem_estatisticas_de("radar_transacao")


@pytest.mark.django_db
def test_abas_filtra():
    _carregar(abas=["FEV-2026"])
    assert Transacao.objects.count() == 2


@pytest.mark.django_db
def test_falha_no_meio_da_recarga_nao_apaga_o_mes(monkeypatch):
    """Antes o delete do mês rodava fora de transação: morrer no meio deixava o mês
    apagado e só parcialmente reposto. É a propriedade que a carga por mês garante."""
    _carregar()
    antes = set(Transacao.objects.values_list("id", flat=True))
    assert len(antes) == 12

    original = cmd.Transacao.objects.bulk_create
    chamadas = {"n": 0}

    def morre_na_segunda(objs, **kw):
        chamadas["n"] += 1
        if chamadas["n"] == 2:
            raise RuntimeError("morte simulada no meio da carga")
        return original(objs, **kw)

    monkeypatch.setattr(cmd.Transacao.objects, "bulk_create", morre_na_segunda)

    with pytest.raises(RuntimeError):
        _carregar(substituir_mes=True)

    assert set(Transacao.objects.values_list("id", flat=True)) == antes


@pytest.mark.django_db
def test_grava_um_mes_por_vez(monkeypatch):
    """O buffer é de um mês só — é isso que mantém a memória constante quando a
    planilha tem muitos anos. Guarda contra reintroduzir o buffer global."""
    original = cmd._gravar_mes
    vistos = []

    def espiao(por_setor, ano_guia, mes_guia, cont, m, **kw):
        vistos.append(((ano_guia, mes_guia), sum(len(v) for v in por_setor.values())))
        return original(por_setor, ano_guia, mes_guia, cont, m, **kw)

    monkeypatch.setattr(cmd, "_gravar_mes", espiao)
    _carregar()

    assert sorted(vistos) == [((2025, 3), 2), ((2026, 1), 8), ((2026, 2), 2)]


@pytest.mark.django_db
def test_limite_vale_por_aba():
    _carregar(limite=1)
    assert Transacao.objects.count() == 3


@pytest.mark.django_db
def test_limite_com_substituir_mes_recusa():
    """--limite apagaria o mês e reporia só N linhas."""
    with pytest.raises(CommandError):
        _carregar(limite=1, substituir_mes=True)
    with pytest.raises(CommandError):
        _carregar(limite=1, limpar=True)


@pytest.mark.django_db
def test_limpar_e_substituir_mes_sao_exclusivos():
    with pytest.raises(CommandError):
        _carregar(limpar=True, substituir_mes=True)


@pytest.mark.django_db
def test_aba_sem_linhas_validas_nao_apaga_o_mes(monkeypatch):
    """Aba vazia não pode apagar o mês: com a gravação atômica o delete é comitado."""
    _carregar()
    antes = set(Transacao.objects.values_list("id", flat=True))

    original = cmd._ler_aba
    monkeypatch.setattr(cmd, "_ler_aba", lambda *a, **k: (original(*a, **k), {})[1])

    _carregar(substituir_mes=True)
    assert set(Transacao.objects.values_list("id", flat=True)) == antes


# ---- qualidade ampliada: valor irrisório, financiamento e data implausível ----
#
# Planilha própria (não a amostra de 12 linhas usada acima) — os casos de
# borda daqui não têm por que empurrar as contagens já fixadas nos outros
# testes deste arquivo.

D = dt.datetime

LINHAS_QUALIDADE = [
    # A: irrisório puro — VVR "fecha" a base de cálculo, então valor_inconsistente
    # não pega nada; só o valor de origem (R$ 0,01) denuncia a linha.
    [11111111111, "R TESTE A", 100, None, "CENTRO", None, 1000000, "1.Compra e venda",
     0.01, D(2026, 3, 10), 228252, 100, 228252, 228252, None, 0, "1º CRI", 1000,
     "Ativo Predial", 300, 10.0, 1.0, 119, 20, "APARTAMENTO EM CONDOMINIO", 23,
     "RESIDENCIAL VERTICAL", 2010],
    # B: irrisório + financiamento incompatível — o caso real da auditoria
    # (R$ 711,78 declarado, R$ 320.000 financiado), sem VVR pra corrigir nada.
    [22222222222, "R TESTE B", 200, None, "CENTRO", None, 1000000, "1.Compra e venda",
     711.78, D(2026, 3, 12), 0, 100, 0, 711.78, "1.SFH", 320000, "1º CRI", 2000,
     "Ativo Predial", 300, 10.0, 1.0, 91, 20, "APARTAMENTO EM CONDOMINIO", 23,
     "RESIDENCIAL VERTICAL", 2010],
    # C: data implausível puro — resto da linha limpo.
    [33333333333, "R TESTE C", 300, None, "CENTRO", None, 1000000, "1.Compra e venda",
     500000, D(2099, 1, 15), 500000, 100, 500000, 500000, None, 0, "1º CRI", 3000,
     "Ativo Predial", 300, 10.0, 1.0, 150, 20, "APARTAMENTO EM CONDOMINIO", 23,
     "RESIDENCIAL VERTICAL", 2010],
    # D: SQL cancelado — números do ITBI batem (qualidade seria 0), mas a
    # Prefeitura não reconhece mais o cadastro daquele imóvel.
    [44444444444, "R TESTE D", 400, None, "CENTRO", None, 1000000, "1.Compra e venda",
     500000, D(2026, 3, 18), 500000, 100, 500000, 500000, None, 0, "1º CRI", 4000,
     "Cancelado Predial", 300, 10.0, 1.0, 120, 20, "APARTAMENTO EM CONDOMINIO", 23,
     "RESIDENCIAL VERTICAL", 2010],
    # E: Cancelado Territorial — lote-mãe subdividido pra empreendimento novo;
    # deliberadamente NÃO marca qualidade.
    [55555555555, "R TESTE E", 500, None, "CENTRO", None, 1000000, "1.Compra e venda",
     500000, D(2026, 3, 20), 500000, 100, 500000, 500000, None, 0, "1º CRI", 5000,
     "Cancelado Territorial", 300, 10.0, 1.0, 120, 20, "APARTAMENTO EM CONDOMINIO", 23,
     "RESIDENCIAL VERTICAL", 2010],
]


def _planilha_qualidade(tmp_path):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("MAR-2026")
    ws.append(CABECALHO)
    for linha in LINHAS_QUALIDADE:
        ws.append(linha)
    caminho = tmp_path / "qualidade.xlsx"
    wb.save(caminho)
    return caminho


@pytest.mark.django_db
def test_valor_irrisorio_marca_qualidade_mesmo_com_vvr_corrigindo_base(tmp_path):
    carregar(str(_planilha_qualidade(tmp_path)), base_dir_geo=str(GEO), blocos=3)
    t = Transacao.objects.get(sql="11111111111")
    assert t.qualidade == 4


@pytest.mark.django_db
def test_financiamento_maior_que_valor_declarado_marca_qualidade(tmp_path):
    carregar(str(_planilha_qualidade(tmp_path)), base_dir_geo=str(GEO), blocos=3)
    t = Transacao.objects.get(sql="22222222222")
    assert t.valor_financiado == 320000
    assert t.qualidade == 4 + 8  # irrisório + financiamento incompatível


@pytest.mark.django_db
def test_data_implausivel_marca_qualidade(tmp_path):
    carregar(str(_planilha_qualidade(tmp_path)), base_dir_geo=str(GEO), blocos=3)
    t = Transacao.objects.get(sql="33333333333")
    assert t.qualidade == 16


@pytest.mark.django_db
def test_sql_cancelado_marca_qualidade_e_guarda_situacao(tmp_path):
    carregar(str(_planilha_qualidade(tmp_path)), base_dir_geo=str(GEO), blocos=3)
    t = Transacao.objects.get(sql="44444444444")
    assert t.situacao_sql == "Cancelado Predial"
    assert t.qualidade == 32


@pytest.mark.django_db
def test_cancelado_territorial_guarda_situacao_mas_nao_marca_qualidade(tmp_path):
    carregar(str(_planilha_qualidade(tmp_path)), base_dir_geo=str(GEO), blocos=3)
    t = Transacao.objects.get(sql="55555555555")
    assert t.situacao_sql == "Cancelado Territorial"
    assert t.qualidade == 0
