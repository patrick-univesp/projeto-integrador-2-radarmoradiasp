"""Carrega a planilha de guias de ITBI pagas no banco.

Lê o ``.xlsx`` em streaming (sem ``pandas``), minera cada linha com
``radar/carga/`` e resolve ``lat``/``lon``/``distrito`` por *lookup* na referência
versionada (``radar/carga/geo_ref.py``, sem ``shapely``). Grava em blocos com
``bulk_create``. Detalhe: ``docs/carga-itbi.md``.
"""

import resource
import time
from decimal import Decimal

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from radar.carga import coercao, geo_ref, mineracao
from radar.carga.normalizacao import normalizar_bairro
from radar.models import Transacao

# Posição das 28 colunas na aba mensal (lidas por posição: FEV-2026 tem uma
# coluna extra vazia e o cabeçalho do padrão vem com typo).
(C_SQL, C_LOGR, C_NUM, C_COMPL, C_BAIRRO, C_REF, C_CEP, C_NATUREZA,
 C_VALOR, C_DATA, C_VVR, C_PROP, C_VVRP, C_BASE, C_TIPOFIN, C_VALFIN,
 C_CARTORIO, C_MATRIC, C_SITSQL, C_ATERR, C_TESTADA, C_FRACAO, C_ACONSTR,
 C_USOCOD, C_USODESC, C_PADRCOD, C_PADRDESC, C_ACC) = range(28)


def _dec(x, *, obrigatorio=True):
    """``float`` → ``Decimal`` com 2 casas. ``None`` vira ``0.00`` num campo
    obrigatório (fica marcado por ``qualidade``) e ``None`` num anulável."""
    if x is None:
        return Decimal("0.00") if obrigatorio else None
    return Decimal(f"{float(x):.2f}")


def _linha_para_transacao(bruta, indices, ano_guia, mes_guia):
    sql = coercao.para_sql(bruta[C_SQL])
    if not sql:
        return None

    prop = coercao.para_numero(bruta[C_PROP])
    vvrp = coercao.para_numero(bruta[C_VVRP])
    valor = coercao.para_numero(bruta[C_VALOR])
    base = coercao.para_numero(bruta[C_BASE])
    area = coercao.para_numero(bruta[C_ACONSTR])
    uso_cod = coercao.para_numero(bruta[C_USOCOD])
    data = coercao.para_data(bruta[C_DATA])
    natureza = coercao.para_texto(bruta[C_NATUREZA])
    tipofin = coercao.para_texto(bruta[C_TIPOFIN])
    logr = coercao.para_texto(bruta[C_LOGR])
    bairro = coercao.para_texto(bruta[C_BAIRRO])

    lon, lat, nivel, distrito, _sub, _reg = geo_ref.resolver(sql, logr, bruta[C_NUM], indices)

    deslocada = mineracao.linha_deslocada(bruta[C_SITSQL], bruta[C_TIPOFIN])
    inconsistente = mineracao.valor_inconsistente(base, valor, vvrp)

    return Transacao(
        sql=sql,
        logradouro=logr[:150],
        numero=coercao.para_numero_porta(bruta[C_NUM])[:10],
        complemento=coercao.para_texto(bruta[C_COMPL])[:40],
        bairro=bairro[:120],
        bairro_norm=normalizar_bairro(bairro)[:120],
        cep=coercao.para_cep(bruta[C_CEP]),
        distrito=(distrito or "")[:60],
        lat=lat,
        lon=lon,
        geo_nivel=nivel,
        valor_transacao=_dec(valor),
        base_calculo=_dec(base),
        data_transacao=data,
        ano_transacao=mineracao.ano_transacao(data),
        area_construida=_dec(area, obrigatorio=False),
        uso_grupo=mineracao.grupo_de_uso(uso_cod)[:40],
        rs_m2_construido=_dec(mineracao.rs_m2_construido(base, area, prop), obrigatorio=False),
        qualidade=mineracao.qualidade(deslocada, inconsistente),
        flag_cadastro_defasado=mineracao.cadastro_defasado(natureza, tipofin, prop, uso_cod),
        ano_guia=ano_guia,
        mes_guia=mes_guia,
    )


def _abas_mensais(wb):
    return [a for a in wb.sheetnames if len(a) == 8 and a[3] == "-" and a[:3].isalpha()]


def _pico_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


_CONTADORES = ("lidas", "gravadas", "descartadas", "ruins", "sem_geo")


def carregar(arquivo, abas=None, *, blocos=2000, limite=None, substituir_mes=False,
             limpar=False, dry_run=False, sem_geo=False, base_dir_geo=None, progresso=None):
    """Carga completa. Lê o ``.xlsx`` uma vez e agrupa as linhas por setor
    fiscal, para carregar a referência geo de **um setor por vez** (~poucos MB)
    em vez da cidade inteira (~450 MB). ``progresso(dict)`` roda a cada bloco e no
    fim de cada setor. Devolve o resumo — é esta função que a tela de admin reusa.
    """
    t0 = time.monotonic()
    wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
    disponiveis = _abas_mensais(wb)
    alvo = [a for a in disponiveis if a in abas] if abas else disponiveis
    if abas and not alvo:
        wb.close()
        raise CommandError(f"nenhuma das abas {abas} existe em {arquivo} (tem: {disponiveis})")

    cont = dict.fromkeys(_CONTADORES, 0)
    # setor -> [(bruta, ano_guia, mes_guia), ...]
    por_setor: dict[str, list] = {}
    meses = set()
    for aba in alvo:
        ano_guia, mes_guia = int(aba[4:]), coercao.mes_guia(aba)
        meses.add((ano_guia, mes_guia))
        n = 0
        for bruta in wb[aba].iter_rows(min_row=2, values_only=True):
            if bruta[C_SQL] is None:
                continue
            if limite and n >= limite:
                break
            n += 1
            cont["lidas"] += 1
            sql = coercao.para_sql(bruta[C_SQL])
            if not sql:
                cont["descartadas"] += 1
                continue
            por_setor.setdefault(sql[:3], []).append((bruta, ano_guia, mes_guia))
    wb.close()

    if not dry_run:
        if limpar:
            Transacao.objects.all().delete()
        elif substituir_mes:
            for ano_guia, mes_guia in meses:
                Transacao.objects.filter(ano_guia=ano_guia, mes_guia=mes_guia).delete()

    lote = []
    for setor in sorted(por_setor):
        indices = ({}, {}, {}, {}) if sem_geo else geo_ref.indices_de_setor(setor, base_dir_geo)
        for bruta, ano_guia, mes_guia in por_setor[setor]:
            obj = _linha_para_transacao(bruta, indices, ano_guia, mes_guia)
            if obj.qualidade:
                cont["ruins"] += 1
            if obj.geo_nivel == "--":
                cont["sem_geo"] += 1
            lote.append(obj)
            if len(lote) >= blocos:
                if not dry_run:
                    with transaction.atomic():
                        Transacao.objects.bulk_create(lote, batch_size=blocos)
                cont["gravadas"] += len(lote)
                lote.clear()
                if progresso:
                    progresso(dict(cont))
    if lote:
        if not dry_run:
            with transaction.atomic():
                Transacao.objects.bulk_create(lote, batch_size=blocos)
        cont["gravadas"] += len(lote)

    resumo = {"total": cont, "setores": len(por_setor),
              "segundos": round(time.monotonic() - t0, 1), "pico_mb": round(_pico_mb())}
    if progresso:
        progresso({"fim": True, **cont})
    return resumo


class Command(BaseCommand):
    help = "Carrega a planilha de guias de ITBI pagas no banco."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo", required=True)
        parser.add_argument("--abas", help="lista separada por vírgula (padrão: todas)")
        parser.add_argument("--blocos", type=int, default=2000)
        parser.add_argument("--limite", type=int, help="só as N primeiras linhas por aba")
        parser.add_argument("--limpar", action="store_true", help="apaga tudo antes")
        parser.add_argument("--substituir-mes", action="store_true",
                            help="apaga as linhas do mes_guia+ano de cada aba antes de inserir")
        parser.add_argument("--sem-geo", action="store_true",
                            help="não resolve lat/lon/distrito (tudo '--') — feedback rápido")
        parser.add_argument("--dry-run", action="store_true", help="parseia e valida sem gravar")

    def handle(self, *_args, **o):
        abas = [a.strip() for a in o["abas"].split(",")] if o["abas"] else None

        def progresso(ev):
            if not ev.get("fim"):
                self.stdout.write(
                    f"  {ev['gravadas']} gravadas ({ev['ruins']} qualidade!=0, "
                    f"{ev['sem_geo']} sem geo)", ending="\r"
                )

        try:
            r = carregar(
                o["arquivo"], abas, blocos=o["blocos"], limite=o["limite"],
                substituir_mes=o["substituir_mes"], limpar=o["limpar"],
                dry_run=o["dry_run"], sem_geo=o["sem_geo"], progresso=progresso,
            )
        except FileNotFoundError as e:
            raise CommandError(str(e)) from e

        t = r["total"]
        self.stdout.write(self.style.SUCCESS(
            f"\n{t['lidas']} lidas · {t['gravadas']} gravadas · {t['descartadas']} sem SQL · "
            f"{t['ruins']} qualidade!=0 · {t['sem_geo']} sem geo\n"
            f"{r['segundos']}s · pico de memória {r['pico_mb']} MB"
            + ("  (dry-run: nada gravado)" if o["dry_run"] else "")
        ))
